/** Create the label renderer without any DSH slot or service dependency. */
export function createModelLabel(React, VERSIONS) {
	const wrapStyle = {
		display: "inline-flex",
		alignItems: "center",
		gap: "4px",
		whiteSpace: "nowrap",
		verticalAlign: "baseline"
	};
	const pillStyle = {
		display: "inline-block",
		padding: "0 6px",
		borderRadius: "999px",
		fontSize: "11px",
		lineHeight: "16px",
		fontWeight: 500,
		background: "rgba(59, 130, 246, 0.12)",
		color: "#3b82f6",
		letterSpacing: "0.02em"
	};
	/**
	 * Decorate official DeepSeek model labels with a structured snapshot badge.
	 *
	 * @param props.provider Provider identity (`{ id, name }`), provided by the model control.
	 * @param props.model    Catalog model entry (`{ id, name }`), provided by the model control.
	 * @returns The untouched catalog name when no published version is known.
	 */
	function ModelVersionBadge({ provider, model }) {
		// Only official DeepSeek channels carry published snapshot versions.
		const isDeepSeek = typeof provider?.id === "string" && provider.id.indexOf("deepseek") === 0;
		const hit = isDeepSeek ? VERSIONS[model.id] : void 0;
		if (!hit) return model.name;
		return React.createElement("span", {
			style: wrapStyle,
			// Full official name on hover, e.g. "DeepSeek-V4.1-Flash-1017".
			title: hit.full
		}, React.createElement("span", null, model.name), " ", React.createElement("span", {
			style: pillStyle
		}, hit.badge));
	}
	return ModelVersionBadge;
}
