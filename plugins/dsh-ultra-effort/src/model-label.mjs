/** Create the label renderer without any DSH slot or service dependency. */
export function createModelLabel(React, VERSIONS) {
	const wrapStyle = {
		display: "inline-flex",
		alignItems: "center",
		gap: "4px",
		maxWidth: "100%",
		minWidth: 0,
		whiteSpace: "nowrap",
		verticalAlign: "baseline"
	};
	const triggerWrapStyle = {
		...wrapStyle,
		gap: "3px"
	};
	/**
	 * Decorate model labels with DSH 0.2.2+ catalog `model.badge` first,
	 * falling back to the bundled DeepSeek snapshot version table when absent.
	 *
	 * @param props.providerId  Optional provider id string.
	 * @param props.provider    Provider identity (`{ id, name }`), provided by the model control.
	 * @param props.model       Catalog model entry (`{ id, name, badge? }`).
	 * @param props.placement   Render surface (`"trigger" | "menu" | "option"`).
	 * @param props.resolveText Optional DSH `ctx.locale.resolveText` resolver for localized badge text.
	 */
	function ModelVersionBadge({ providerId, provider, model, placement = "option", resolveText }) {
		const isTrigger = placement === "trigger";
		if (model?.badge !== void 0 && model.badge !== null) {
			const raw = model.badge.text;
			const badgeText = typeof resolveText === "function"
				? resolveText(raw)
				: (typeof raw === "string" ? raw : raw?.zh ?? raw?.en ?? "");
			if (!badgeText) return model.name;
			const tone = model.badge.tone || "neutral";
			return React.createElement("span", {
				className: "ue-model-label" + (isTrigger ? " ue-model-labelTrigger" : ""),
				style: isTrigger ? triggerWrapStyle : wrapStyle,
				title: model.name + " · " + badgeText
			}, React.createElement("span", {
				className: "ue-model-labelName"
			}, model.name), " ", React.createElement("span", {
				className: "ue-ver-badge",
				"data-tone": tone
			}, badgeText));
		}
		// Fallback: only official DeepSeek channels carry bundled snapshot versions.
		const pid = providerId ?? provider?.id;
		const isDeepSeek = typeof pid === "string" && pid.indexOf("deepseek") === 0;
		const hit = isDeepSeek ? VERSIONS[model.id] : void 0;
		if (!hit) return model.name;
		return React.createElement("span", {
			className: "ue-model-label" + (isTrigger ? " ue-model-labelTrigger" : ""),
			style: isTrigger ? triggerWrapStyle : wrapStyle,
			// Full official name on hover, e.g. "DeepSeek-V4.1-Flash-1017".
			title: hit.full
		}, React.createElement("span", {
			className: "ue-model-labelName"
		}, model.name), " ", React.createElement("span", {
			className: "ue-ver-badge",
			"data-tone": "info"
		}, hit.badge));
	}
	return ModelVersionBadge;
}
