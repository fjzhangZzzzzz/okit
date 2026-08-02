package cli

// mobaActionResult is the stable machine result for mutating MobaXterm actions.
// It deliberately represents plan, cancellation and completion through one shape.
type mobaActionResult struct {
	SchemaVersion int    `json:"schema_version"`
	Action        string `json:"action"`
	Status        string `json:"status"`
	Changed       bool   `json:"changed"`
	Plan          bool   `json:"plan"`
}

const (
	mobaStatusPlanned   = "planned"
	mobaStatusCancelled = "cancelled"
	mobaStatusCompleted = "completed"
	mobaStatusUnchanged = "unchanged"
)

func newMobaActionResult(action, status string) mobaActionResult {
	result := mobaActionResult{SchemaVersion: 1, Action: action, Status: status}
	switch status {
	case mobaStatusPlanned:
		result.Plan = true
	case mobaStatusCompleted:
		result.Changed = true
	}
	return result
}

func mobaMutationResult(action string, dryRun, changed bool) mobaActionResult {
	if dryRun {
		return newMobaActionResult(action, mobaStatusPlanned)
	}
	if changed {
		return newMobaActionResult(action, mobaStatusCompleted)
	}
	return newMobaActionResult(action, mobaStatusUnchanged)
}

func mobaCancelledResult(action string) mobaActionResult {
	return newMobaActionResult(action, mobaStatusCancelled)
}

type mobaThemeApplyResult struct {
	mobaActionResult
	Theme      string `json:"theme"`
	ConfigPath string `json:"config_path"`
	BackupPath string `json:"backup_path,omitempty"`
}

type mobaThemeRestoreResult struct {
	mobaActionResult
	BackupPath string `json:"backup_path"`
	ConfigPath string `json:"config_path"`
}

type mobaLicenseDeployResult struct {
	mobaActionResult
	Username string `json:"username"`
	Version  string `json:"version,omitempty"`
	Result   string `json:"result,omitempty"`
}

type mobaCacheResult struct {
	SchemaVersion int    `json:"schema_version"`
	Status        string `json:"status,omitempty"`
	Path          string `json:"path"`
	Exists        bool   `json:"exists,omitempty"`
	Modified      string `json:"modified,omitempty"`
}

type mobaLicenseGenerateResult struct {
	SchemaVersion int    `json:"schema_version"`
	Status        string `json:"status"`
	Output        string `json:"output"`
	Username      string `json:"username"`
	Version       string `json:"version"`
}

type mobaLicenseVerifyResult struct {
	SchemaVersion int    `json:"schema_version"`
	Valid         bool   `json:"valid"`
	Username      string `json:"username"`
	Version       string `json:"version"`
}
