package cli

import (
	"context"
	"testing"

	"github.com/fjzhangZzzzzz/okit/internal/installation"
)

func TestUpgradeWorkflowReturnsStableStatusMatrix(t *testing.T) {
	cases := []struct {
		name        string
		app         *App
		options     upgradeOptions
		lifecycle   installation.Result
		needsRunner bool
		wantMode    string
		wantStatus  upgradeStatus
	}{
		{name: "development build", app: New("dev"), wantMode: "apply", wantStatus: upgradeStatusUnsupported},
		{name: "invalid installation", app: NewBuildMode("broken", "", "", BuildModeRelease), wantMode: "apply", wantStatus: upgradeStatusInvalidInstallation},
		{name: "check available", app: New("v1.0.0"), options: upgradeOptions{check: true}, lifecycle: installation.Result{Current: "v1.0.0", Available: "v1.1.0"}, needsRunner: true, wantMode: "check", wantStatus: upgradeStatusAvailable},
		{name: "dry run", app: New("v1.0.0"), options: upgradeOptions{dryRun: true}, lifecycle: installation.Result{Current: "v1.0.0", Available: "v1.1.0", Plan: "would update"}, needsRunner: true, wantMode: "dry_run", wantStatus: upgradeStatusPlanned},
		{name: "apply", app: New("v1.0.0"), lifecycle: installation.Result{Current: "v1.0.0", Available: "v1.1.0", Updated: true}, needsRunner: true, wantMode: "apply", wantStatus: upgradeStatusApplied},
		{name: "scheduled", app: New("v1.0.0"), lifecycle: installation.Result{Current: "v1.0.0", Available: "v1.1.0", Updated: true, Scheduled: true}, needsRunner: true, wantMode: "apply", wantStatus: upgradeStatusScheduled},
		{name: "up to date", app: New("v1.0.0"), lifecycle: installation.Result{Current: "v1.0.0", Available: "v1.0.0"}, needsRunner: true, wantMode: "apply", wantStatus: upgradeStatusUpToDate},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			if testCase.needsRunner {
				testCase.app.upgradeRunner = &fakeUpgradeRunner{result: testCase.lifecycle}
			}
			result, err := testCase.app.newUpgradeWorkflow(testCase.options, "json", false, nil).Run(context.Background())
			if err != nil || result.Mode != testCase.wantMode || result.Status != testCase.wantStatus {
				t.Fatalf("result=%+v err=%v", result, err)
			}
		})
	}
}
