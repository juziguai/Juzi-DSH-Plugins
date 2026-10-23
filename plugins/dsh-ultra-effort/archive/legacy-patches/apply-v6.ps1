$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
$css = [System.IO.File]::ReadAllText("D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\build\v6.css.txt", [System.Text.Encoding]::UTF8).TrimEnd()

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new); Write-Output ("ok: " + $name)
}

# 1) 整段替换我们的样式表
$rx = [regex]'const ULTRA_CSS = `[\s\S]*?`;'
if ($rx.Matches($t).Count -ne 1) { throw "css block not unique" }
$t = $rx.Replace($t, ("const ULTRA_CSS = ``" + "`r`n" + $css + "`r`n" + "``;").Replace('$', '$$'), 1)
Write-Output "ok: css"

# 2) 移除上游 base CSS 中与设计冲突的 !important（共 12 处）
$t = $t.Replace("border-radius:9px!important", "border-radius:9px")
$t = $t.Replace("border-radius:9px 0 0 9px!important", "border-radius:9px 0 0 9px")
$t = $t.Replace("width:4px!important;height:4px!important;min-width:0!important;min-height:0!important;flex:none!important;border-radius:50%!important;background:transparent!important;", "width:4px;height:4px;min-width:0;min-height:0;flex:none;border-radius:50%;background:transparent;")
Write-Output ("ok: base-important, remaining=" + ([regex]::Matches($t, '!important')).Count)

# 3) panelRef
$refAnchor = "				const tipBoxRef = react.useRef(null);"
Rep $refAnchor ($refAnchor + "`r`n				const panelRef = react.useRef(null);") "panel-ref"

# 4) levelLabel
$lvlAnchor = '				const safePosIdx = choices.length > 0 ? Math.max(0, Math.min(choices.length - 1, posIdx)) : 0;'
Rep $lvlAnchor ($lvlAnchor + "`r`n				/** 面板内常驻档位名：与滑动/键盘位置同源。 */" + "`r`n" + '				const levelLabel = choices.length > 0 ? choices[safePosIdx].label : tr("effort.default");') "level-label"

# 5) 面板 ref
Rep '					className: "sk5-drop sk5-effort ue-panel",' ('					ref: panelRef,' + "`r`n" + '					className: "sk5-drop sk5-effort ue-panel",') "panel-element-ref"

# 6) 标题行 + 档位徽标
$titleOld = 'react.createElement("div", { className: "ue-center" }, react.createElement("div", { className: "ue-ultra" }, "Ultra"), react.createElement("button", {'
$titleNew = 'react.createElement("div", { className: "ue-center" }, react.createElement("div", { className: "ue-titleRow" }, react.createElement("div", { className: "ue-ultra" }, "Ultra"), react.createElement("span", { key: levelLabel, className: "ue-level" }, levelLabel)), react.createElement("button", {'
Rep $titleOld $titleNew "level-badge"

# 7) PageUp / PageDown
Rep '					else if (ev.key === "Home") next = 0;' ('					else if (ev.key === "PageUp") next = Math.min(choices.length - 1, safePosIdx + 2);' + "`r`n" + '					else if (ev.key === "PageDown") next = Math.max(0, safePosIdx - 2);' + "`r`n" + '					else if (ev.key === "Home") next = 0;') "page-keys"

# 8) 定位/高度/压缩 + 焦点管理：替换旧的 lift effect
$oldLift = @'
				/** 面板锚点在座位（位于输入框内部），只上移 6px 会压住输入框；这里量出输入框高度再抬升。 */
				react.useLayoutEffect(() => {
					const root = rootRef.current;
					if (root === null) return;
					if (menu === null) {
						root.style.removeProperty("--ue-drop-lift");
						return;
					}
					const rootRect = root.getBoundingClientRect();
					let node = root.parentElement;
					let lift = 8;
					for (let i = 0; i < 6 && node !== null; i++, node = node.parentElement) {
						const r = node.getBoundingClientRect();
						if (r.height >= 70) {
							lift = Math.max(8, rootRect.top - r.top + 8);
							break;
						}
					}
					root.style.setProperty("--ue-drop-lift", lift + "px");
				}, [menu]);
'@
$newLift = @'
				/**
				 * 面板定位（V6）：
				 * 1) 垂直：抬到输入框之上，留 8px；
				 * 2) 水平：右缘对齐输入框容器右缘（不是座位），左右各留 ≥8px；
				 * 3) 矮窗口：先压缩（ue-compact），仍放不下再内部滚动。
				 */
				react.useLayoutEffect(() => {
					const root = rootRef.current;
					const panel = panelRef.current;
					if (root === null) return;
					if (menu === null) {
						root.style.removeProperty("--ue-drop-lift");
						root.style.removeProperty("--ue-drop-right");
						return;
					}
					const apply = () => {
						const r = root.getBoundingClientRect();
						let node = root.parentElement;
						let composer = null;
						for (let i = 0; i < 6 && node !== null; i++, node = node.parentElement) {
							const b = node.getBoundingClientRect();
							if (b.height >= 70) {
								composer = b;
								break;
							}
						}
						const vw = window.innerWidth;
						const composerTop = composer ? composer.top : r.top;
						root.style.setProperty("--ue-drop-lift", Math.max(8, r.top - composerTop + 8) + "px");
						if (panel === null) return;
						const pw = panel.getBoundingClientRect().width;
						const targetRight = composer ? composer.right : r.right;
						const right = Math.min(Math.max(targetRight, 8 + pw), vw - 8);
						root.style.setProperty("--ue-drop-right", (r.right - right) + "px");
						const avail = Math.max(160, composerTop - 16);
						panel.style.maxHeight = avail + "px";
						panel.classList.toggle("ue-compact", avail < 200);
						panel.style.overflowY = panel.scrollHeight > avail ? "auto" : "";
					};
					apply();
					window.addEventListener("resize", apply);
					return () => window.removeEventListener("resize", apply);
				}, [menu, panelView]);

				/** 焦点：打开面板聚焦滑杆；关闭后回到触发按钮。 */
				const prevMenuRef = react.useRef(null);
				react.useEffect(() => {
					const prev = prevMenuRef.current;
					prevMenuRef.current = menu;
					if (menu === "effort" && panelView === "effort") {
						if (trackRef.current !== null) trackRef.current.focus({ preventScroll: true });
					} else if (menu === null && prev !== null) {
						if (effortTriggerRef.current !== null) effortTriggerRef.current.focus({ preventScroll: true });
					}
				}, [menu, panelView]);
'@
Rep $oldLift $newLift "layout-and-focus"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length + " | !important total=" + ([regex]::Matches($t, '!important')).Count)
