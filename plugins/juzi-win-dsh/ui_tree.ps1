# Private newline-JSON STA worker for Windows UI Automation tree inspection.
# Compiles a small C# helper once per worker process for fast CacheRequest BFS traversal
# with Per-Monitor V2 DPI awareness so all coordinates match physical screen pixels.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName WindowsBase

Add-Type -ReferencedAssemblies @('UIAutomationClient', 'UIAutomationTypes', 'WindowsBase') -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows;
using System.Windows.Automation;

public static class JuziUiTree {
    [DllImport("user32.dll")]
    private static extern IntPtr SetProcessDpiAwarenessContext(IntPtr value);
    [DllImport("shcore.dll")]
    private static extern int SetProcessDpiAwareness(int awareness);
    [DllImport("user32.dll")]
    private static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    private static bool _dpiInitialized = false;

    private static readonly HashSet<string> InteractiveTypes = new HashSet<string>(StringComparer.OrdinalIgnoreCase) {
        "Button", "MenuItem", "RadioButton", "CheckBox", "ComboBox", "Edit",
        "Hyperlink", "TabItem", "ListItem", "TreeItem", "SplitButton",
        "Slider", "DataItem", "Menu", "Spinner"
    };

    private static readonly HashSet<string> LeafSkipExpandTypes = new HashSet<string>(StringComparer.OrdinalIgnoreCase) {
        "Text", "Image", "Separator", "ScrollBar", "Thumb", "ProgressBar"
    };

    public static void InitDpi() {
        if (_dpiInitialized) return;
        _dpiInitialized = true;
        try {
            if (SetProcessDpiAwarenessContext(new IntPtr(-4)) != IntPtr.Zero) return;
        } catch {}
        try {
            if (SetProcessDpiAwareness(2) == 0) return;
        } catch {}
        try {
            SetProcessDPIAware();
        } catch {}
    }

    private static string ShortControlType(ControlType ct) {
        if (ct == null) return "Unknown";
        string prog = ct.ProgrammaticName ?? "";
        if (prog.StartsWith("ControlType.", StringComparison.Ordinal)) {
            return prog.Substring("ControlType.".Length);
        }
        return prog;
    }

    private static string CleanText(string s, int maxLen) {
        if (string.IsNullOrEmpty(s)) return "";
        var sb = new StringBuilder(Math.Min(s.Length, maxLen + 4));
        bool lastSpace = false;
        for (int i = 0; i < s.Length; i++) {
            char c = s[i];
            if (c == '\r' || c == '\n' || c == '\t') c = ' ';
            if (char.IsControl(c)) continue;
            if (c == ' ') {
                if (lastSpace || sb.Length == 0) continue;
                lastSpace = true;
            } else {
                lastSpace = false;
            }
            sb.Append(c);
            if (sb.Length >= maxLen) break;
        }
        string result = sb.ToString().Trim();
        if (s.Trim().Length > maxLen && result.Length >= maxLen) {
            result = result.Substring(0, Math.Max(1, maxLen - 1)) + "\u2026";
        }
        return result;
    }

    private static void AppendJsonString(StringBuilder sb, string s) {
        sb.Append('"');
        if (s != null) {
            for (int i = 0; i < s.Length; i++) {
                char c = s[i];
                switch (c) {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20) {
                            sb.AppendFormat("\\u{0:x4}", (int)c);
                        } else {
                            sb.Append(c);
                        }
                        break;
                }
            }
        }
        sb.Append('"');
    }

    private class QueueItem {
        public AutomationElement Element;
        public int Depth;
        public string ParentInteractiveText;
        public Node Parent;
    }

    // Snapshot-local IDs also name containers omitted by query/region filters.
    private class Node {
        public int Id, Depth;
        public string Type, Name;
        public Node Parent;

        public void AppendLinks(StringBuilder json) {
            json.Append(",\"id\":").Append(Id).Append(",\"parent_id\":");
            if (Parent == null) json.Append("null"); else json.Append(Parent.Id);
            json.Append(",\"depth\":").Append(Depth);
        }
    }

    private static string ReadVisibleText(AutomationElement element, Stopwatch timer,
        int timeoutMs, out bool truncated) {
        truncated = false;
        const int maxChars = 2048;
        try {
            if (element.Current.IsPassword) return null;
            object pattern;
            if (!element.TryGetCurrentPattern(TextPattern.Pattern, out pattern)) return null;
            var ranges = ((TextPattern)pattern).GetVisibleRanges();
            var text = new StringBuilder();
            for (int i = 0; i < ranges.Length; i++) {
                if (i >= 64 || timer.ElapsedMilliseconds >= timeoutMs) {
                    truncated = true;
                    break;
                }
                int remaining = maxChars - text.Length;
                string part = ranges[i].GetText(remaining + 1);
                if (String.IsNullOrEmpty(part)) continue;
                if (text.Length > 0 && remaining > 0) {
                    text.Append('\n');
                    remaining--;
                }
                if (part.Length > remaining) {
                    if (remaining > 0 && Char.IsHighSurrogate(part[remaining - 1])) remaining--;
                    text.Append(part, 0, remaining);
                    truncated = true;
                    break;
                }
                text.Append(part);
            }
            return text.ToString();
        } catch (Exception) {
            // Providers can withdraw a pattern or element between the cached and live calls.
            return null;
        }
    }

    public static string Inspect(
        long hwnd,
        int maxElements,
        int maxDepth,
        bool interactiveOnly,
        bool includeText,
        bool skipOffscreen,
        string query,
        int timeoutMs,
        bool hasRegion,
        int rx, int ry, int rw, int rh,
        bool includeHierarchy, bool includeVisibleText
    ) {
        InitDpi();
        var sw = Stopwatch.StartNew();
        try {
            IntPtr targetHwnd = hwnd > 0 ? new IntPtr(hwnd) : GetForegroundWindow();
            if (targetHwnd == IntPtr.Zero) {
                return "{\"ok\":false,\"error\":\"no_window\",\"message\":\"未找到目标窗口句柄。\"}";
            }

            var cache = new CacheRequest();
            cache.TreeScope = TreeScope.Element | TreeScope.Children;
            cache.TreeFilter = Automation.ControlViewCondition;
            cache.AutomationElementMode = AutomationElementMode.Full;
            cache.Add(AutomationElement.ControlTypeProperty);
            cache.Add(AutomationElement.NameProperty);
            cache.Add(AutomationElement.IsEnabledProperty);
            cache.Add(AutomationElement.IsOffscreenProperty);
            cache.Add(AutomationElement.BoundingRectangleProperty);
            cache.Add(AutomationElement.IsPasswordProperty);
            if (includeVisibleText) {
                cache.Add(AutomationElement.IsTextPatternAvailableProperty);
                cache.Add(AutomationElement.IsValuePatternAvailableProperty);
            }
            cache.Add(AutomationElement.AutomationIdProperty);
            // ValuePattern may contain the entire document, including scrolled-out lines.
            if (!includeVisibleText) cache.Add(ValuePattern.ValueProperty);
            cache.Add(SelectionItemPattern.IsSelectedProperty);
            cache.Add(TogglePattern.ToggleStateProperty);
            cache.Add(ExpandCollapsePattern.ExpandCollapseStateProperty);

            AutomationElement root;
            using (cache.Activate()) {
                root = AutomationElement.FromHandle(targetHwnd);
            }
            if (root == null) {
                return "{\"ok\":false,\"error\":\"uia_unavailable\",\"message\":\"无法从窗口句柄创建 UIA 节点。\"}";
            }

            string queryNorm = string.IsNullOrWhiteSpace(query) ? "" : query.Trim();
            bool hasQuery = queryNorm.Length > 0;
            int maxVisited = hasQuery ? 5000 : Math.Max(1500, maxElements * 12);

            var queue = new Queue<QueueItem>();
            queue.Enqueue(new QueueItem { Element = root, Depth = 0, ParentInteractiveText = "" });

            var itemsJson = new List<string>();
            var compactLines = new List<string>();
            var seenKeys = new HashSet<string>();
            var hierarchy = new SortedDictionary<int, Node>();

            int visited = 0;
            bool truncated = false;

            while (queue.Count > 0) {
                if (itemsJson.Count >= maxElements) {
                    truncated = true;
                    break;
                }
                if (visited >= maxVisited || sw.ElapsedMilliseconds >= timeoutMs) {
                    truncated = true;
                    break;
                }

                var current = queue.Dequeue();
                visited++;

                AutomationElement el = current.Element;
                string typeName;
                string rawName;
                bool isEnabled;
                bool isOffscreen;
                bool isPassword;
                Rect rect;
                string valueText = "";
                bool? isSelected = null;
                string checkedState = null;
                bool? isExpanded = null;

                try {
                    typeName = ShortControlType(el.Cached.ControlType);
                    rawName = el.Cached.Name ?? "";
                    isEnabled = el.Cached.IsEnabled;
                    isOffscreen = el.Cached.IsOffscreen;
                    isPassword = el.Cached.IsPassword;
                    rect = el.Cached.BoundingRectangle;

                    if (!isPassword && !includeVisibleText) {
                        object vObj = el.GetCachedPropertyValue(ValuePattern.ValueProperty, true);
                        if (vObj != AutomationElement.NotSupported && vObj is string) {
                            valueText = CleanText((string)vObj, 120);
                        }
                    }
                    object selObj = el.GetCachedPropertyValue(SelectionItemPattern.IsSelectedProperty, true);
                    if (selObj != AutomationElement.NotSupported && selObj is bool) {
                        isSelected = (bool)selObj;
                    }
                    object togObj = el.GetCachedPropertyValue(TogglePattern.ToggleStateProperty, true);
                    if (togObj != AutomationElement.NotSupported && togObj is ToggleState) {
                        ToggleState ts = (ToggleState)togObj;
                        checkedState = ts == ToggleState.On ? "on" : (ts == ToggleState.Off ? "off" : "indeterminate");
                    }
                    object expObj = el.GetCachedPropertyValue(ExpandCollapsePattern.ExpandCollapseStateProperty, true);
                    if (expObj != AutomationElement.NotSupported && expObj is ExpandCollapseState) {
                        ExpandCollapseState ecs = (ExpandCollapseState)expObj;
                        if (ecs == ExpandCollapseState.Expanded || ecs == ExpandCollapseState.PartiallyExpanded) {
                            isExpanded = true;
                        } else if (ecs == ExpandCollapseState.Collapsed) {
                            isExpanded = false;
                        }
                    }
                } catch {
                    continue;
                }

                string name = CleanText(rawName, 120);
                bool isInteractive = InteractiveTypes.Contains(typeName);
                bool isText = typeName.Equals("Text", StringComparison.OrdinalIgnoreCase)
                    || typeName.Equals("HeaderItem", StringComparison.OrdinalIgnoreCase);

                bool validRect = !rect.IsEmpty
                    && !double.IsInfinity(rect.X) && !double.IsInfinity(rect.Y)
                    && !double.IsInfinity(rect.Width) && !double.IsInfinity(rect.Height)
                    && rect.Width >= 2 && rect.Height >= 2;

                int x = validRect ? (int)Math.Round(rect.X) : 0;
                int y = validRect ? (int)Math.Round(rect.Y) : 0;
                int w = validRect ? (int)Math.Round(rect.Width) : 0;
                int h = validRect ? (int)Math.Round(rect.Height) : 0;
                int cx = validRect ? (int)Math.Round(rect.X + rect.Width / 2.0) : 0;
                int cy = validRect ? (int)Math.Round(rect.Y + rect.Height / 2.0) : 0;

                bool inRegion = !hasRegion || (validRect && cx >= rx && cx <= rx + rw && cy >= ry && cy <= ry + rh);
                bool visibleOk = (!skipOffscreen || !isOffscreen) && validRect;
                Node node = includeHierarchy ? new Node {
                    Id = visited, Parent = current.Parent, Depth = current.Depth, Type = typeName, Name = name
                } : null;
                string visibleText = null;
                bool textTruncated = false;
                if (includeVisibleText && !isPassword && visibleOk && inRegion && (!interactiveOnly || isInteractive)) {
                    bool hasText = (bool)el.GetCachedPropertyValue(AutomationElement.IsTextPatternAvailableProperty);
                    if (hasText) {
                        visibleText = ReadVisibleText(el, sw, timeoutMs, out textTruncated);
                    } else if ((bool)el.GetCachedPropertyValue(AutomationElement.IsValuePatternAvailableProperty)) {
                        // Query a value only for this value-only control. Never fall back
                        // to a document's full value when reading its visible ranges fails.
                        try {
                            if (!el.Current.IsPassword &&
                                !(bool)el.GetCurrentPropertyValue(AutomationElement.IsTextPatternAvailableProperty)) {
                                valueText = CleanText(el.GetCurrentPropertyValue(ValuePattern.ValueProperty, true) as string, 120);
                            }
                        } catch (Exception) { /* A live provider can disappear after the cached lookup. */ }
                    }
                }

                bool shouldEmit = false;
                if (current.Depth > 0 && visibleOk && inRegion) {
                    if (isInteractive) {
                        shouldEmit = true;
                    } else if (!interactiveOnly && includeText && isText && name.Length > 0) {
                        if (string.IsNullOrEmpty(current.ParentInteractiveText)
                            || !string.Equals(name, current.ParentInteractiveText, StringComparison.OrdinalIgnoreCase)) {
                            shouldEmit = true;
                        }
                    } else if (hasQuery && !interactiveOnly && (name.Length > 0 || valueText.Length > 0)) {
                        shouldEmit = true;
                    }
                }

                if (visibleText != null) shouldEmit = true;
                if (shouldEmit && hasQuery) {
                    bool matchName = name.IndexOf(queryNorm, StringComparison.OrdinalIgnoreCase) >= 0;
                    bool matchVal = valueText.IndexOf(queryNorm, StringComparison.OrdinalIgnoreCase) >= 0;
                    bool matchText = visibleText != null && visibleText.IndexOf(queryNorm, StringComparison.OrdinalIgnoreCase) >= 0;
                    if (!matchName && !matchVal && !matchText) {
                        shouldEmit = false;
                    }
                }

                if (shouldEmit) {
                    // Deduplicate identical control type + text at nearly the same center.
                    string dedupKey = typeName + "|" + name + "|" + valueText + "|" + (cx / 4) + "|" + (cy / 4);
                    if (node != null && node.Parent != null) dedupKey = node.Parent.Id + "|" + dedupKey;
                    if (seenKeys.Add(dedupKey)) {
                        var js = new StringBuilder(192);
                        js.Append("{\"type\":"); AppendJsonString(js, typeName);
                        js.Append(",\"name\":"); AppendJsonString(js, name);
                        if (node != null) {
                            node.AppendLinks(js);
                            for (Node n = node; n != null && !hierarchy.ContainsKey(n.Id); n = n.Parent)
                                hierarchy.Add(n.Id, n);
                        }
                        if (visibleText != null) {
                            js.Append(",\"visible_text\":"); AppendJsonString(js, visibleText);
                            js.Append(",\"visible_text_truncated\":").Append(textTruncated ? "true" : "false");
                        }
                        js.Append(",\"cx\":").Append(cx).Append(",\"cy\":").Append(cy);
                        js.Append(",\"rect\":{\"x\":").Append(x).Append(",\"y\":").Append(y)
                          .Append(",\"width\":").Append(w).Append(",\"height\":").Append(h).Append('}');
                        js.Append(",\"enabled\":").Append(isEnabled ? "true" : "false");
                        if (isPassword) {
                            js.Append(",\"is_password\":true");
                        } else if (valueText.Length > 0 && !string.Equals(valueText, name, StringComparison.Ordinal)) {
                            js.Append(",\"value\":"); AppendJsonString(js, valueText);
                        }
                        if (isSelected.HasValue && isSelected.Value) {
                            js.Append(",\"selected\":true");
                        }
                        if (checkedState != null) {
                            js.Append(",\"checked\":"); AppendJsonString(js, checkedState);
                        }
                        if (isExpanded.HasValue) {
                            js.Append(",\"expanded\":").Append(isExpanded.Value ? "true" : "false");
                        }
                        js.Append('}');
                        itemsJson.Add(js.ToString());

                        var line = new StringBuilder(128);
                        line.Append(typeName);
                        if (name.Length > 0) {
                            line.Append(" \"").Append(name.Replace("\"", "'")).Append('"');
                        }
                        if (!isPassword && valueText.Length > 0 && !string.Equals(valueText, name, StringComparison.Ordinal)) {
                            line.Append(" val=\"").Append(valueText.Replace("\"", "'")).Append('"');
                        }
                        line.Append(" (").Append(cx).Append(',').Append(cy).Append(')');
                        if (!isEnabled) line.Append(" [DISABLED]");
                        if (isSelected.HasValue && isSelected.Value) line.Append(" [selected]");
                        if (checkedState != null) line.Append(" [checked=").Append(checkedState).Append(']');
                        if (isExpanded.HasValue) line.Append(isExpanded.Value ? " [expanded]" : " [collapsed]");
                        if (isPassword) line.Append(" [password]");
                        if (visibleText != null) {
                            line.Append(" text="); AppendJsonString(line, visibleText);
                            if (textTruncated) line.Append(" [text truncated]");
                        }
                        compactLines.Add(line.ToString());
                    }
                }

                // Decide whether to enqueue children
                bool canDescend = !isPassword && current.Depth < maxDepth
                    && !LeafSkipExpandTypes.Contains(typeName)
                    && !(skipOffscreen && isOffscreen && current.Depth > 2);

                if (canDescend) {
                    AutomationElementCollection children = null;
                    try {
                        if (current.Depth == 0) {
                            children = el.CachedChildren;
                        } else {
                            // Refresh cache on this container to pre-fetch its children in one COM call.
                            using (cache.Activate()) {
                                AutomationElement refreshed = el.GetUpdatedCache(cache);
                                children = refreshed != null ? refreshed.CachedChildren : null;
                            }
                        }
                    } catch {
                        children = null;
                    }

                    if (children != null && children.Count > 0) {
                        string nextParentText = isInteractive && name.Length > 0 ? name : current.ParentInteractiveText;
                        for (int i = 0; i < children.Count; i++) {
                            queue.Enqueue(new QueueItem {
                                Element = children[i],
                                Depth = current.Depth + 1,
                                Parent = node,
                                ParentInteractiveText = nextParentText
                            });
                        }
                    }
                }
            }

            sw.Stop();
            var outSb = new StringBuilder(itemsJson.Count * 160 + 256);
            outSb.Append("{\"ok\":true,\"hwnd\":").Append(targetHwnd.ToInt64());
            outSb.Append(",\"count\":").Append(itemsJson.Count);
            outSb.Append(",\"visited_nodes\":").Append(visited);
            outSb.Append(",\"truncated\":").Append(truncated ? "true" : "false");
            outSb.Append(",\"elapsed_ms\":").Append(sw.ElapsedMilliseconds);
            outSb.Append(",\"coordinate_space\":\"screen-physical-pixels\"");
            outSb.Append(",\"compact\":"); AppendJsonString(outSb, string.Join("\n", compactLines));
            if (includeHierarchy) {
                outSb.Append(",\"hierarchy\":[");
                bool first = true;
                foreach (Node n in hierarchy.Values) {
                    if (!first) outSb.Append(',');
                    first = false;
                    outSb.Append("{\"type\":"); AppendJsonString(outSb, n.Type);
                    outSb.Append(",\"name\":"); AppendJsonString(outSb, n.Name);
                    n.AppendLinks(outSb);
                    outSb.Append('}');
                }
                outSb.Append(']');
            }
            outSb.Append(",\"elements\":[");
            for (int i = 0; i < itemsJson.Count; i++) {
                if (i > 0) outSb.Append(',');
                outSb.Append(itemsJson[i]);
            }
            outSb.Append("]}");
            return outSb.ToString();
        } catch (Exception ex) {
            sw.Stop();
            var err = new StringBuilder(256);
            err.Append("{\"ok\":false,\"error\":\"uia_failed\",\"elapsed_ms\":").Append(sw.ElapsedMilliseconds);
            err.Append(",\"message\":"); AppendJsonString(err, ex.Message);
            err.Append('}');
            return err.ToString();
        }
    }
}
"@

[JuziUiTree]::InitDpi()

while ($null -ne ($line = [Console]::ReadLine())) {
    $trimmed = $line.Trim()
    if (-not $trimmed) { continue }
    try {
        $req = $trimmed | ConvertFrom-Json
        $hwnd = if ($null -ne $req.hwnd) { [long]$req.hwnd } else { 0L }
        $maxElements = if ($null -ne $req.max_elements) { [int]$req.max_elements } else { 150 }
        $maxDepth = if ($null -ne $req.max_depth) { [int]$req.max_depth } else { 12 }
        $interactiveOnly = if ($null -ne $req.interactive_only) { [bool]$req.interactive_only } else { $false }
        $includeText = if ($null -ne $req.include_text) { [bool]$req.include_text } else { $true }
        $skipOffscreen = if ($null -ne $req.skip_offscreen) { [bool]$req.skip_offscreen } else { $true }
        $query = if ($null -ne $req.query) { [string]$req.query } else { "" }
        $timeoutMs = if ($null -ne $req.timeout_ms) { [int]$req.timeout_ms } else { 2500 }
        $hasRegion = $false
        $rx = 0; $ry = 0; $rw = 0; $rh = 0
        if ($null -ne $req.region) {
            $hasRegion = $true
            $rx = [int]$req.region.x
            $ry = [int]$req.region.y
            $rw = [int]$req.region.width
            $rh = [int]$req.region.height
        }
        $json = [JuziUiTree]::Inspect($hwnd, $maxElements, $maxDepth, $interactiveOnly, $includeText, $skipOffscreen, $query, $timeoutMs, $hasRegion, $rx, $ry, $rw, $rh, [bool]$req.include_hierarchy, [bool]$req.include_visible_text)
        [Console]::WriteLine($json)
    } catch {
        $msg = $_.Exception.Message -replace '"', "'"
        [Console]::WriteLine("{`"ok`":false,`"error`":`"uia_worker_error`",`"message`":`"$msg`"}")
    }
    [Console]::Out.Flush()
    $req = $null
    $line = $null
}
