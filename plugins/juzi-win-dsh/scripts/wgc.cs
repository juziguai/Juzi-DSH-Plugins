using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Threading;
using System.Threading.Tasks;
using Windows.Foundation;
using Windows.Graphics.Capture;
using Windows.Graphics.DirectX;
using Windows.Graphics.DirectX.Direct3D11;
using Windows.Graphics.Imaging;
using Windows.Storage;

// Loaded on the first WGC request in the OCR worker. The MCP process never owns GPU handles.
public static class JuziWindowCapture
{
    [ComImport, Guid("3628E81B-3CAC-4C60-B7F4-23CE0E0C3356"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface ICaptureItemInterop
    {
        [PreserveSig]
        int CreateForWindow(IntPtr hwnd, ref Guid iid, out IntPtr item);
    }

    [DllImport("d3d11.dll")]
    private static extern int D3D11CreateDevice(IntPtr adapter, int driverType, IntPtr software,
        uint flags, IntPtr levels, uint levelCount, uint sdkVersion, out IntPtr device,
        IntPtr featureLevel, IntPtr immediateContext);

    [DllImport("d3d11.dll")]
    private static extern int CreateDirect3D11DeviceFromDXGIDevice(IntPtr dxgi, out IntPtr device);

    private static IDirect3DDevice CreateDevice()
    {
        IntPtr native = IntPtr.Zero, dxgi = IntPtr.Zero, projected = IntPtr.Zero;
        try {
            // Hardware device, BGRA support, D3D11_SDK_VERSION.
            Marshal.ThrowExceptionForHR(D3D11CreateDevice(IntPtr.Zero, 1, IntPtr.Zero, 0x20,
                IntPtr.Zero, 0, 7, out native, IntPtr.Zero, IntPtr.Zero));
            var iid = new Guid("54EC77FA-1377-44E6-8C32-88FD5F44C84C"); // IDXGIDevice
            Marshal.ThrowExceptionForHR(Marshal.QueryInterface(native, ref iid, out dxgi));
            Marshal.ThrowExceptionForHR(CreateDirect3D11DeviceFromDXGIDevice(dxgi, out projected));
            return (IDirect3DDevice)Marshal.GetObjectForIUnknown(projected);
        } finally {
            if (projected != IntPtr.Zero) Marshal.Release(projected);
            if (dxgi != IntPtr.Zero) Marshal.Release(dxgi);
            if (native != IntPtr.Zero) Marshal.Release(native);
        }
    }

    private static GraphicsCaptureItem WindowItem(long hwnd)
    {
        var interop = (ICaptureItemInterop)WindowsRuntimeMarshal.GetActivationFactory(typeof(GraphicsCaptureItem));
        var iid = new Guid("79C3F95B-31F7-4EC2-A464-632EF5D30760"); // IGraphicsCaptureItem
        IntPtr item;
        Marshal.ThrowExceptionForHR(interop.CreateForWindow(new IntPtr(hwnd), ref iid, out item));
        try { return (GraphicsCaptureItem)Marshal.GetObjectForIUnknown(item); }
        finally { Marshal.Release(item); }
    }

    // The OS ships per-namespace WinMDs. Use their WinRT async interfaces directly
    // instead of the .NET AsTask projection that requires the SDK's combined Windows.winmd.
    private static void WaitFor(IAsyncInfo operation)
    {
        var timeout = Stopwatch.StartNew();
        while (operation.Status == AsyncStatus.Started) {
            if (timeout.ElapsedMilliseconds >= 5000) {
                operation.Cancel();
                throw new TimeoutException("WGC image transfer timed out.");
            }
            Thread.Sleep(5);
        }
    }

    private static T Result<T>(IAsyncOperation<T> operation)
    {
        WaitFor(operation);
        return operation.GetResults();
    }

    public static void SavePng(long hwnd, int frameWidth, int frameHeight, int x, int y,
        int width, int height, string outputPath)
    {
        // The OCR worker is STA. Run the full capture and WinRT async transfers on
        // an MTA thread so synchronous PowerShell callers do not starve COM callbacks.
        Task.Run(() => Capture(hwnd, frameWidth, frameHeight, x, y, width, height, outputPath))
            .GetAwaiter().GetResult();
    }

    private static void Capture(long hwnd, int frameWidth, int frameHeight, int x, int y,
        int width, int height, string outputPath)
    {
        if (!GraphicsCaptureSession.IsSupported())
            throw new PlatformNotSupportedException("Windows Graphics Capture is unavailable.");
        var item = WindowItem(hwnd);
        var size = item.Size;
        if (x < 0 || y < 0 || width <= 0 || height <= 0 ||
            width > frameWidth - x || height > frameHeight - y)
            throw new InvalidOperationException("Requested area is outside the WGC window.");
        // item.Size can include invisible resize borders. ContentSize on the delivered
        // frame is what must match the DWM physical bounds used for the crop.
        size.Width = Math.Max(size.Width, frameWidth);
        size.Height = Math.Max(size.Height, frameHeight);

        using (var device = CreateDevice())
        using (var pool = Direct3D11CaptureFramePool.CreateFreeThreaded(device,
                DirectXPixelFormat.B8G8R8A8UIntNormalized, 1, size))
        using (var session = pool.CreateCaptureSession(item)) {
            var cursorCapture = typeof(GraphicsCaptureSession).GetProperty("IsCursorCaptureEnabled");
            if (cursorCapture != null) cursorCapture.SetValue(session, false, null);
            session.StartCapture();
            var timer = Stopwatch.StartNew();
            while (timer.ElapsedMilliseconds < 3000) {
                using (var frame = pool.TryGetNextFrame()) {
                    if (frame != null) {
                        if (frame.ContentSize.Width != frameWidth || frame.ContentSize.Height != frameHeight)
                            throw new InvalidOperationException(String.Format("WGC content {0}x{1}, expected DWM bounds {2}x{3}.",
                                frame.ContentSize.Width, frame.ContentSize.Height, frameWidth, frameHeight));
                        var file = Result(StorageFile.GetFileFromPathAsync(outputPath));
                        using (var bitmap = Result(SoftwareBitmap.CreateCopyFromSurfaceAsync(frame.Surface)))
                        using (var stream = Result(file.OpenAsync(FileAccessMode.ReadWrite))) {
                            var encoder = Result(BitmapEncoder.CreateAsync(BitmapEncoder.PngEncoderId, stream));
                            encoder.SetSoftwareBitmap(bitmap);
                            encoder.BitmapTransform.Bounds = new BitmapBounds {
                                X = (uint)x, Y = (uint)y, Width = (uint)width, Height = (uint)height
                            };
                            var flush = encoder.FlushAsync();
                            WaitFor(flush);
                            flush.GetResults();
                        }
                        return;
                    }
                }
                Thread.Sleep(10);
            }
            throw new TimeoutException("No WGC frame received within 3 seconds.");
        }
    }
}
