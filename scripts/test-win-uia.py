"""Opt-in Windows desktop smoke for inspect_ui. Run with python scripts/test-win-uia.py."""

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "juzi-win-dsh"
FIXTURE = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
$markup = '<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
 Title="Juzi inspection fixture" Width="480" Height="450" ShowActivated="False"
 Topmost="True" ShowInTaskbar="False" WindowStartupLocation="CenterScreen">
 <StackPanel Margin="10">
  <GroupBox Header="Order Alpha"><Button Content="Delete"/></GroupBox>
  <GroupBox Header="Order Beta"><Button Content="Delete"/></GroupBox>
  <TextBox Name="Editor" AutomationProperties.Name="Fixture editor" Height="48"
   AcceptsReturn="True" VerticalScrollBarVisibility="Visible" FontSize="16"/>
  <TextBox Name="LongEditor" AutomationProperties.Name="Long sample" Height="145" FontSize="5" TextWrapping="Wrap"/>
  <ComboBox AutomationProperties.Name="Fixture choice" IsEditable="True" SelectedIndex="0">
   <ComboBoxItem>Channel 5462</ComboBoxItem>
  </ComboBox>
  <PasswordBox Name="Secret" AutomationProperties.Name="Fixture password"/>
 </StackPanel></Window>'
$window = [Windows.Markup.XamlReader]::Parse($markup)
$editor = $window.FindName('Editor')
$editor.Text = (@('Hidden header 7615') + (1..12 | ForEach-Object { "Earlier $_" }) +
  @('Run 4821', 'Second line') + (1..35 | ForEach-Object { "Later $_" }) + 'Offscreen 9630') -join [Environment]::NewLine
$window.FindName('LongEditor').Text = 'field ' * 500
$window.FindName('Secret').Password = 'PrivateFixture7391'
$window.Show()
$window.UpdateLayout()
$editor.ScrollToLine(13)
$window.UpdateLayout()
$timer = New-Object Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(100)
$deadline = [DateTime]::UtcNow.AddSeconds(45)
$timer.Add_Tick({ if ((Test-Path -LiteralPath $env:JUZI_UIA_TEST_STOP) -or [DateTime]::UtcNow -gt $deadline) { $window.Close() } })
$timer.Start()
$window.Add_Closed({ $timer.Stop(); $window.Dispatcher.InvokeShutdown() })
[Console]::WriteLine(([Windows.Interop.WindowInteropHelper]::new($window)).Handle.ToInt64())
[Console]::Out.Flush()
[Windows.Threading.Dispatcher]::Run()
"""


def inspect_fixture(hwnd):
    calls = [
        {"query": "Delete", "interactive_only": True, "include_elements": True},
        {"query": "Fixture editor", "include_visible_text": True, "include_elements": True},
        {"query": "Fixture password", "include_visible_text": True, "include_elements": True},
        {"query": "Run 4821", "include_visible_text": True},
        {"query": "Delete"},
        {"query": "Delete", "include_elements": True, "max_elements": 1},
        {"query": "Hidden header 7615", "include_elements": True, "include_visible_text": True},
        {"query": "Long sample", "include_elements": True, "include_visible_text": True},
        {"query": "Channel 5462", "include_elements": True, "include_visible_text": True},
    ]
    requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}]
    for number, arguments in enumerate(calls, 2):
        requests.append({"jsonrpc": "2.0", "id": number, "method": "tools/call", "params": {
            "name": "inspect_ui", "arguments": {"hwnd": hwnd, **arguments}}})
    process = subprocess.run(
        [sys.executable, "-B", str(PLUGIN / "server.py")],
        input="".join(json.dumps(request) + "\n" for request in requests),
        capture_output=True, text=True, encoding="utf-8", timeout=35, check=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    responses = [json.loads(line) for line in process.stdout.splitlines()]
    return [json.loads(response["result"]["content"][0]["text"]) for response in responses[1:]]


def check_results(results):
    tree, editor, password, compact, legacy, limited, hidden, long_text, choice = results
    assert all(result.get("ok") for result in results), [result.get("error_code") for result in results]
    for snapshot in (tree, limited):
        nodes = {node["id"]: node for node in snapshot["hierarchy"]}
        groups = []
        for element in snapshot["elements"]:
            assert element["type"] == "Button" and element["name"] == "Delete"
            node = nodes[element["id"]]
            assert node["parent_id"] == element["parent_id"]
            while node["parent_id"] is not None:
                parent = nodes[node["parent_id"]]
                assert parent["depth"] + 1 == node["depth"]
                if parent["type"] == "Group":
                    groups.append(parent["name"])
                node = parent
            assert node["depth"] == 0
        if snapshot is tree:
            assert sorted(groups) == ["Order Alpha", "Order Beta"], groups
        else:
            assert limited["count"] == 1 and limited["truncated"]
    text = editor["elements"][0]["visible_text"]
    assert "Run 4821" in text and "Offscreen 9630" not in text, repr(text)
    assert "Hidden header 7615" not in json.dumps(editor)
    assert hidden["count"] == 0 and hidden["hierarchy"] == []
    combo = next(item for item in choice["elements"] if item["type"] == "ComboBox")
    assert combo["name"] == "Fixture choice" and combo["value"] == "Channel 5462"
    assert "visible_text" not in combo
    assert "value" not in editor["elements"][0]
    long_item = long_text["elements"][0]
    assert len(long_item["visible_text"]) == 2048 and long_item["visible_text_truncated"]
    assert "Run 4821" in compact["compact"] and "elements" not in compact
    assert "elements" not in legacy and "hierarchy" not in legacy
    assert password["elements"][0]["is_password"]
    assert "visible_text" not in password["elements"][0]
    assert "PrivateFixture7391" not in json.dumps(results)


def main():
    with tempfile.TemporaryDirectory(prefix=".tmp-juzi-uia-") as directory:
        stop = Path(directory) / "stop"
        command = base64.b64encode(FIXTURE.encode("utf-16-le")).decode("ascii")
        with subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-EncodedCommand", command],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW,
            env={**os.environ, "JUZI_UIA_TEST_STOP": str(stop)},
        ) as fixture:
            try:
                line = fixture.stdout.readline()
                if not line:
                    raise RuntimeError(fixture.stderr.read().decode(errors="replace"))
                check_results(inspect_fixture(int(line)))
            finally:
                stop.touch()
                try:
                    fixture.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    fixture.kill()
    print("UIA_SMOKE_OK")


if __name__ == "__main__":
    main()
