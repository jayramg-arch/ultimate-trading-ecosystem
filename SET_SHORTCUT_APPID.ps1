# Set System.AppUserModel.ID on a .lnk so the taskbar treats it as its own app.
#
# WHY (12-Aug-2026): the Commander launcher shortcut targets cmd.exe, so Windows
# groups the RUNNING window under Command Prompt instead of merging it into the
# pinned icon - you end up with a pinned tile that never lights up and a second
# console button next to it. An explicit AppUserModelID gives the shortcut its
# own taskbar identity; Windows applies that ID to the process the shortcut
# launches and CHILD PROCESSES INHERIT IT, so cmd -> python -> streamlit all
# stay under the one icon.
#
# WScript.Shell cannot do this - it exposes no property store. The ID lives in
# the shortcut's IPropertyStore under PKEY_AppUserModel_ID
# ({9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}, pid 5), which needs COM interop.
#
#   powershell -ExecutionPolicy Bypass -File SET_SHORTCUT_APPID.ps1
#   powershell -ExecutionPolicy Bypass -File SET_SHORTCUT_APPID.ps1 -Path "x.lnk" -AppId "My.App"
#
# AFTER RUNNING: unpin and re-pin the shortcut. The taskbar caches the identity
# at pin time, so an already-pinned tile keeps the old grouping until re-pinned.

param(
    [string[]] $Path,
    [string]   $AppId = "JayramG.WeinsteinCommander"
)

$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace ShellLnk {

[StructLayout(LayoutKind.Sequential)]
public struct PropertyKey {
    public Guid fmtid;
    public uint pid;
    public PropertyKey(Guid f, uint p) { fmtid = f; pid = p; }
}

[StructLayout(LayoutKind.Sequential)]
public struct PropVariant {
    public ushort vt;
    public ushort r1, r2, r3;
    public IntPtr p;
    public int p2;
}

[ComImport, Guid("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPropertyStore {
    int GetCount(out uint c);
    int GetAt(uint i, out PropertyKey k);
    int GetValue(ref PropertyKey k, out PropVariant v);
    int SetValue(ref PropertyKey k, ref PropVariant v);
    int Commit();
}

[ComImport, Guid("0000010b-0000-0000-C000-000000000046"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPersistFile {
    int GetClassID(out Guid pClassID);
    int IsDirty();
    int Load([MarshalAs(UnmanagedType.LPWStr)] string f, uint mode);
    int Save([MarshalAs(UnmanagedType.LPWStr)] string f, [MarshalAs(UnmanagedType.Bool)] bool remember);
    int SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string f);
    int GetCurFile([MarshalAs(UnmanagedType.LPWStr)] out string f);
}

[ComImport, Guid("00021401-0000-0000-C000-000000000046")]
public class ShellLink { }

public static class Setter {
    // PKEY_AppUserModel_ID
    static readonly Guid FMTID = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");
    const ushort VT_LPWSTR = 31;

    public static string Apply(string lnkPath, string appId) {
        object o = new ShellLink();
        IPersistFile pf = (IPersistFile)o;
        int hr = pf.Load(lnkPath, 2 /* STGM_READWRITE */);
        if (hr != 0) throw new Exception("Load failed 0x" + hr.ToString("X8"));

        IPropertyStore ps = (IPropertyStore)o;
        PropertyKey key = new PropertyKey(FMTID, 5);
        PropVariant pv = new PropVariant();
        pv.vt = VT_LPWSTR;
        pv.p = Marshal.StringToCoTaskMemUni(appId);
        try {
            hr = ps.SetValue(ref key, ref pv);
            if (hr != 0) throw new Exception("SetValue failed 0x" + hr.ToString("X8"));
            hr = ps.Commit();
            if (hr != 0) throw new Exception("Commit failed 0x" + hr.ToString("X8"));
            hr = pf.Save(lnkPath, true);
            if (hr != 0) throw new Exception("Save failed 0x" + hr.ToString("X8"));
        } finally {
            Marshal.FreeCoTaskMem(pv.p);
            Marshal.ReleaseComObject(o);
        }
        return Read(lnkPath);
    }

    public static string Read(string lnkPath) {
        object o = new ShellLink();
        IPersistFile pf = (IPersistFile)o;
        if (pf.Load(lnkPath, 0 /* STGM_READ */) != 0) return "<load failed>";
        IPropertyStore ps = (IPropertyStore)o;
        PropertyKey key = new PropertyKey(FMTID, 5);
        PropVariant pv;
        string val = "<none>";
        if (ps.GetValue(ref key, out pv) == 0 && pv.vt == VT_LPWSTR && pv.p != IntPtr.Zero)
            val = Marshal.PtrToStringUni(pv.p);
        Marshal.ReleaseComObject(o);
        return val;
    }
}
}
'@

if (-not $Path -or $Path.Count -eq 0) {
    $desktop  = [Environment]::GetFolderPath('Desktop')
    $programs = [Environment]::GetFolderPath('Programs')
    $Path = @(
        (Join-Path $desktop  'Weinstein Commander.lnk'),
        (Join-Path $programs 'Weinstein Commander\Weinstein Commander.lnk'),
        # If it is already pinned, the taskbar keeps its OWN copy - stamp that one
        # too or the live window still groups separately.
        (Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\Weinstein Commander.lnk')
    )
}

foreach ($p in $Path) {
    if (-not (Test-Path $p)) { Write-Host "  skip (not found): $p"; continue }
    $before = [ShellLnk.Setter]::Read($p)
    $after  = [ShellLnk.Setter]::Apply($p, $AppId)
    $ok = if ($after -eq $AppId) { "OK" } else { "MISMATCH" }
    Write-Host ("  {0,-8} {1}`n           was: {2}  now: {3}" -f $ok, (Split-Path $p -Leaf), $before, $after)
}

Write-Host ""
Write-Host "  Unpin and re-pin the shortcut - the taskbar caches identity at pin time."
