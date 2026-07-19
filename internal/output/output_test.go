package output

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
)

func TestRenderDocument(t *testing.T) {
	var stdout, stderr bytes.Buffer
	presenter := New(&stdout, &stderr, Policy{Format: FormatTable})
	err := presenter.Render(View{Human: Document{
		Title:  "Update available",
		Fields: []Field{{Label: "Current", Value: "v1.0.0"}, {Label: "Latest", Value: "v1.1.0"}},
		Hint:   "Run `okit self update` to install.",
	}})
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"Update available", "Current:", "v1.0.0", "Latest:", "Run `okit self update`"} {
		if !strings.Contains(stdout.String(), want) {
			t.Fatalf("output does not contain %q: %q", want, stdout.String())
		}
	}
}

func TestQuietKeepsResultAndSuppressesHint(t *testing.T) {
	var stdout bytes.Buffer
	presenter := New(&stdout, &bytes.Buffer{}, Policy{Format: FormatTable, Quiet: true})
	if err := presenter.Render(View{Human: Document{Title: "Updated", Hint: "Next step"}}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(stdout.String(), "Updated") || strings.Contains(stdout.String(), "Next step") {
		t.Fatalf("quiet output=%q", stdout.String())
	}
}

func TestJSONIsValidAndDoesNotUseHumanDocument(t *testing.T) {
	var stdout bytes.Buffer
	presenter := New(&stdout, &bytes.Buffer{}, Policy{Format: FormatJSON})
	payload := map[string]any{"status": "ok", "items": []string{}}
	if err := presenter.Render(View{Human: Document{Title: "human"}, Machine: payload}); err != nil {
		t.Fatal(err)
	}
	var decoded map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &decoded); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if strings.Contains(stdout.String(), "human") {
		t.Fatalf("JSON contains human output: %q", stdout.String())
	}
}

func TestEmptyStateIsExplicit(t *testing.T) {
	var stdout bytes.Buffer
	presenter := New(&stdout, &bytes.Buffer{}, Policy{Format: FormatTable})
	if err := presenter.Render(View{Human: Document{Empty: &EmptyState{Message: "No values found.", Hint: "Configure one."}}}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(stdout.String(), "No values found") || !strings.Contains(stdout.String(), "Configure one") {
		t.Fatalf("empty output=%q", stdout.String())
	}
}

func TestMachineDiagnosticIsJSON(t *testing.T) {
	var stderr bytes.Buffer
	New(&bytes.Buffer{}, &stderr, Policy{Format: FormatJSON}).Error(Diagnostic{Code: "TEST", Message: "failed", Action: "retry"})
	var payload map[string]any
	if err := json.Unmarshal(stderr.Bytes(), &payload); err != nil {
		t.Fatalf("invalid diagnostic JSON: %v: %q", err, stderr.String())
	}
	if payload["level"] != "error" || payload["code"] != "TEST" {
		t.Fatalf("payload=%v", payload)
	}
	if payload["action"] != "retry" {
		t.Fatalf("action=%v", payload["action"])
	}
	if _, exists := payload["hint"]; exists {
		t.Fatalf("legacy hint field is still exposed: %v", payload)
	}
}

func TestHumanDiagnosticUsesNaturalLanguage(t *testing.T) {
	var stderr bytes.Buffer
	presenter := New(&bytes.Buffer{}, &stderr, Policy{Format: FormatTable})
	presenter.Error(Diagnostic{Code: "TEST_FAILURE", Message: "Something went wrong.", Action: "Try again."})
	if stderr.String() != "Something went wrong.\n\nTry again.\n" {
		t.Fatalf("stderr=%q", stderr.String())
	}
	for _, technical := range []string{"error:", "hint:", "TEST_FAILURE"} {
		if strings.Contains(stderr.String(), technical) {
			t.Fatalf("human diagnostic leaked %q: %q", technical, stderr.String())
		}
	}
}

func TestVerboseHumanDiagnosticIncludesTechnicalContext(t *testing.T) {
	var stderr bytes.Buffer
	presenter := New(&bytes.Buffer{}, &stderr, Policy{Format: FormatTable, Verbose: true})
	presenter.Error(Diagnostic{Code: "TEST_FAILURE", Message: "Something went wrong.", Fields: map[string]string{"command": "okit test"}})
	for _, want := range []string{"Something went wrong.", "Diagnostic level: error", "Diagnostic code: TEST_FAILURE", "command: okit test"} {
		if !strings.Contains(stderr.String(), want) {
			t.Fatalf("verbose diagnostic does not contain %q: %q", want, stderr.String())
		}
	}
}
