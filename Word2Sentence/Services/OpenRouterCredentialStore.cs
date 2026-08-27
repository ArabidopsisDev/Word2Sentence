using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

namespace Word2Sentence.Services;

public static class OpenRouterCredentialStore
{
    private const string TargetName = "Word2Sentence/OpenRouter";
    private const uint CredentialTypeGeneric = 1;
    private const uint CredentialPersistLocalMachine = 2;

    public static string? ReadApiKey()
    {
        if (!CredRead(TargetName, CredentialTypeGeneric, 0, out var credentialPointer)) return null;

        try
        {
            var credential = Marshal.PtrToStructure<NativeCredential>(credentialPointer);
            if (credential.CredentialBlob == IntPtr.Zero || credential.CredentialBlobSize == 0) return null;
            var bytes = new byte[credential.CredentialBlobSize];
            Marshal.Copy(credential.CredentialBlob, bytes, 0, bytes.Length);
            return Encoding.UTF8.GetString(bytes).Trim();
        }
        finally
        {
            CredFree(credentialPointer);
        }
    }

    public static void SaveApiKey(string apiKey)
    {
        var normalized = apiKey.Trim();
        var bytes = Encoding.UTF8.GetBytes(normalized);
        var blobPointer = Marshal.AllocCoTaskMem(bytes.Length);
        try
        {
            Marshal.Copy(bytes, 0, blobPointer, bytes.Length);
            var credential = new NativeCredential
            {
                Type = CredentialTypeGeneric,
                TargetName = TargetName,
                CredentialBlobSize = (uint)bytes.Length,
                CredentialBlob = blobPointer,
                Persist = CredentialPersistLocalMachine,
                UserName = Environment.UserName
            };
            if (!CredWrite(ref credential, 0))
                throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        finally
        {
            Array.Clear(bytes);
            if (blobPointer != IntPtr.Zero)
            {
                for (var index = 0; index < bytes.Length; index++) Marshal.WriteByte(blobPointer, index, 0);
                Marshal.FreeCoTaskMem(blobPointer);
            }
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NativeCredential
    {
        public uint Flags;
        public uint Type;
        public string TargetName;
        public string? Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public uint CredentialBlobSize;
        public IntPtr CredentialBlob;
        public uint Persist;
        public uint AttributeCount;
        public IntPtr Attributes;
        public string? TargetAlias;
        public string UserName;
    }

    [DllImport("advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CredRead(string target, uint type, uint flags, out IntPtr credentialPointer);

    [DllImport("advapi32.dll", EntryPoint = "CredWriteW", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CredWrite([In] ref NativeCredential userCredential, uint flags);

    [DllImport("advapi32.dll")]
    private static extern void CredFree(IntPtr credentialPointer);
}
