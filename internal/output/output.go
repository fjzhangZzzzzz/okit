package output

import (
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"text/tabwriter"
)

const (
	FormatTable = "table"
	FormatJSON  = "json"
	FormatJSONL = "jsonl"
	FormatCSV   = "csv"
	FormatRaw   = "raw"
)

type Policy struct {
	Format  string
	Quiet   bool
	Verbose bool
	NoColor bool
}

type Presenter struct {
	stdout io.Writer
	stderr io.Writer
	policy Policy
}

func New(stdout, stderr io.Writer, policy Policy) *Presenter {
	return &Presenter{stdout: stdout, stderr: stderr, policy: policy}
}

type Field struct {
	Label string
	Value string
}

type Table struct {
	Headers []string
	Rows    [][]string
}

type PlanItem struct {
	Action   string
	Resource string
	Target   string
}

type EmptyState struct {
	Message string
	Hint    string
}

type Document struct {
	Title   string
	Fields  []Field
	Table   *Table
	Lines   []string
	Plan    []PlanItem
	Empty   *EmptyState
	Summary string
	Hint    string
}

type View struct {
	Human   Document
	Machine any
}

func (p *Presenter) Render(view View) error {
	switch p.policy.Format {
	case FormatJSON:
		if view.Machine == nil {
			return fmt.Errorf("JSON output is unavailable for this result")
		}
		encoder := json.NewEncoder(p.stdout)
		encoder.SetIndent("", "  ")
		return encoder.Encode(view.Machine)
	case FormatJSONL:
		values, ok := view.Machine.([]any)
		if !ok {
			return fmt.Errorf("JSONL output requires a result sequence")
		}
		encoder := json.NewEncoder(p.stdout)
		for _, value := range values {
			if err := encoder.Encode(value); err != nil {
				return err
			}
		}
		return nil
	default:
		return p.renderDocument(view.Human)
	}
}

func (p *Presenter) Raw(text string) error {
	_, err := io.WriteString(p.stdout, text)
	return err
}

func (p *Presenter) Prompt(text string) error {
	_, err := io.WriteString(p.stderr, text)
	return err
}

func (p *Presenter) Error(d Diagnostic) {
	writeDiagnostic(p.stderr, p.policy.Format, "error", d)
}

func (p *Presenter) Warning(d Diagnostic) {
	writeDiagnostic(p.stderr, p.policy.Format, "warning", d)
}

func (p *Presenter) Verbose(message string, fields ...Field) {
	if !p.policy.Verbose {
		return
	}
	fmt.Fprintf(p.stderr, "diagnostic: %s\n", message)
	for _, field := range fields {
		fmt.Fprintf(p.stderr, "  %s: %s\n", field.Label, field.Value)
	}
}

func (p *Presenter) renderDocument(document Document) error {
	wrote := false
	writeLine := func(value string) {
		fmt.Fprintln(p.stdout, value)
		wrote = true
	}
	blank := func() {
		if wrote {
			fmt.Fprintln(p.stdout)
		}
	}

	if document.Title != "" {
		writeLine(document.Title)
	}
	if document.Empty != nil {
		if wrote {
			blank()
		}
		writeLine(document.Empty.Message)
		if document.Empty.Hint != "" && !p.policy.Quiet {
			blank()
			writeLine(document.Empty.Hint)
		}
		return nil
	}
	if len(document.Fields) > 0 {
		if wrote {
			blank()
		}
		writer := tabwriter.NewWriter(p.stdout, 0, 4, 2, ' ', 0)
		for _, field := range document.Fields {
			fmt.Fprintf(writer, "%s:\t%s\n", field.Label, valueOrDash(field.Value))
		}
		if err := writer.Flush(); err != nil {
			return err
		}
		wrote = true
	}
	if document.Table != nil {
		if wrote {
			blank()
		}
		if err := writeTable(p.stdout, *document.Table); err != nil {
			return err
		}
		wrote = true
	}
	if len(document.Plan) > 0 {
		if wrote {
			blank()
		}
		table := Table{Headers: []string{"ACTION", "RESOURCE", "TARGET"}}
		for _, item := range document.Plan {
			table.Rows = append(table.Rows, []string{item.Action, item.Resource, item.Target})
		}
		if err := writeTable(p.stdout, table); err != nil {
			return err
		}
		wrote = true
	}
	if len(document.Lines) > 0 {
		if wrote {
			blank()
		}
		for _, line := range document.Lines {
			writeLine(line)
		}
	}
	if document.Summary != "" {
		if wrote {
			blank()
		}
		writeLine(document.Summary)
	}
	if document.Hint != "" && !p.policy.Quiet {
		if wrote {
			blank()
		}
		writeLine(document.Hint)
	}
	return nil
}

func writeTable(w io.Writer, table Table) error {
	writer := tabwriter.NewWriter(w, 0, 4, 2, ' ', 0)
	if len(table.Headers) > 0 {
		if _, err := fmt.Fprintln(writer, strings.Join(table.Headers, "\t")); err != nil {
			return err
		}
	}
	for _, row := range table.Rows {
		if _, err := fmt.Fprintln(writer, strings.Join(row, "\t")); err != nil {
			return err
		}
	}
	return writer.Flush()
}

func valueOrDash(value string) string {
	if value == "" {
		return "-"
	}
	return value
}
