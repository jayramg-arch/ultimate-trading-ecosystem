using System;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.Threading;

namespace RRGStudioLauncher
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            int port = 8502;
            string url = "http://localhost:" + port;

            bool isRunning = IsPortOpen("127.0.0.1", port, 500);

            if (!isRunning)
            {
                // Launch background Streamlit server
                ProcessStartInfo startInfo = new ProcessStartInfo
                {
                    FileName = "python.exe",
                    Arguments = "-m streamlit run rrg_studio/app.py --server.port=8502 --server.headless=true",
                    WorkingDirectory = baseDir,
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    WindowStyle = ProcessWindowStyle.Hidden
                };

                try
                {
                    Process.Start(startInfo);
                }
                catch
                {
                    // Fallback to py.exe or cmd
                    ProcessStartInfo fallbackInfo = new ProcessStartInfo
                    {
                        FileName = "cmd.exe",
                        Arguments = "/c python -m streamlit run rrg_studio/app.py --server.port=8502 --server.headless=true",
                        WorkingDirectory = baseDir,
                        CreateNoWindow = true,
                        UseShellExecute = false,
                        WindowStyle = ProcessWindowStyle.Hidden
                    };
                    Process.Start(fallbackInfo);
                }

                // Wait up to 5 seconds for server to bind
                for (int i = 0; i < 10; i++)
                {
                    Thread.Sleep(500);
                    if (IsPortOpen("127.0.0.1", port, 300))
                    {
                        break;
                    }
                }
            }

            // Open default browser to RRG Studio
            try
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = url,
                    UseShellExecute = true
                });
            }
            catch { }
        }

        static bool IsPortOpen(string host, int port, int timeoutMs)
        {
            try
            {
                using (var client = new TcpClient())
                {
                    var result = client.BeginConnect(host, port, null, null);
                    bool success = result.AsyncWaitHandle.WaitOne(timeoutMs);
                    if (!success) return false;
                    client.EndConnect(result);
                    return true;
                }
            }
            catch
            {
                return false;
            }
        }
    }
}
