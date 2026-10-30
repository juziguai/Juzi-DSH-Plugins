# Private newline-JSON worker; types are initialized once per owned STA process.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class JuziFocusNative {
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [StructLayout(LayoutKind.Sequential)] public struct GUIInfo {
  public uint size, flags; public IntPtr active, focus, capture, menu, move, caret;
  public int left, top, right, bottom;
 }
 [DllImport("user32.dll")] static extern bool GetGUIThreadInfo(uint id, ref GUIInfo info);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr hwnd, System.Text.StringBuilder name, int max);
 [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
 [DllImport("user32.dll", EntryPoint="GetWindowLongW")] static extern int GetWindowLong(IntPtr hwnd, int index);
 [DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern IntPtr SendMessageTimeout(IntPtr hwnd, uint msg, UIntPtr length, System.Text.StringBuilder text, uint flags, uint timeout, out UIntPtr result);
 public static IntPtr Focus() { var info=new GUIInfo(); info.size=(uint)Marshal.SizeOf(info); if(!GetGUIThreadInfo(0, ref info)) throw new Exception("focus_unavailable"); return info.focus; }
 public static string ReadNative(long expected, int max) {
  var hwnd=Focus(); var value=ReadControl(hwnd,expected,max);
  if(Focus()!=hwnd) throw new Exception("target_changed");
  return value;
 }
 public static string ReadControl(IntPtr hwnd,long expected,int max) {
  if(GetAncestor(hwnd,2).ToInt64()!=expected) throw new Exception("target_changed"); var name=new System.Text.StringBuilder(256); GetClassName(hwnd,name,256);
  var cls=name.ToString();
  if (!(cls.Equals("Edit",StringComparison.OrdinalIgnoreCase) || cls.StartsWith("WindowsForms10.EDIT.",StringComparison.OrdinalIgnoreCase))) throw new Exception("focused_text_unavailable");
  if ((GetWindowLong(hwnd,-16)&0x20)!=0) throw new Exception("password_control");
  var text=new System.Text.StringBuilder(max+2); UIntPtr count;
  if(SendMessageTimeout(hwnd,13,(UIntPtr)(max+2),text,2,500,out count)==IntPtr.Zero) throw new Exception("native_read_timeout");
  return text.ToString();
 }
 public static bool Editable() { return (GetWindowLong(Focus(),-16)&0x800)==0; }
}
"@
function Read-FocusedText([long]$ExpectedHwnd, [int]$MaxChars) {
$identity = $null
$method = 'uia'
try {
 if ([long][JuziFocusNative]::GetForegroundWindow() -ne $ExpectedHwnd) { throw 'target_changed' }
 $element = [System.Windows.Automation.AutomationElement]::FocusedElement
 if ($null -eq $element) { throw 'focused_text_unavailable' }
 if ($element.Current.IsPassword) { throw 'password_control' }
 $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$ExpectedHwnd)
 if ($element.Current.ProcessId -ne $root.Current.ProcessId) { throw 'target_changed' }
 $identity = ($element.GetRuntimeId() -join ',')
 $pattern = $null
 $value = $null
 $editable = $false
 try {
 if ($element.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
   $value = $pattern.Current.Value
   $editable = -not $pattern.Current.IsReadOnly
 } elseif ($element.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern, [ref]$pattern)) {
   $value = $pattern.DocumentRange.GetText($MaxChars + 1)
   $editable = $element.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit
 } else { throw 'uia_pattern_unavailable' }
 } catch {
   $value = [JuziFocusNative]::ReadNative($ExpectedHwnd, $MaxChars)
   $editable = [JuziFocusNative]::Editable()
   $method = 'wm_gettext'
 }
 if ([long][JuziFocusNative]::GetForegroundWindow() -ne $ExpectedHwnd -or ([System.Windows.Automation.AutomationElement]::FocusedElement.GetRuntimeId() -join ',') -ne $identity) { throw 'target_changed' }
 @{ok=$true; text=$value.Substring(0, [Math]::Min($value.Length,$MaxChars)); truncated=($value.Length -gt $MaxChars); focus_id=$identity; editable=$editable; control_type=$element.Current.ControlType.ProgrammaticName; read_method=$method} | ConvertTo-Json -Compress
} catch {
 @{ok=$false; error=$(if ($_.Exception.Message -match 'password_control') {'password_control'} elseif ($_.Exception.Message -match 'target_changed') {'target_changed'} else {'focused_text_unavailable'}); focus_id=$identity; message=$_.Exception.Message} | ConvertTo-Json -Compress
}
}

while ($null -ne ($line = [Console]::ReadLine())) {
 $request = $line | ConvertFrom-Json
 if ($request.max_chars -lt 1 -or $request.max_chars -gt 100000) { throw 'invalid_max_chars' }
 [Console]::WriteLine((Read-FocusedText ([long]$request.hwnd) ([int]$request.max_chars)))
 [Console]::Out.Flush()
 $request = $null
 $line = $null
}
