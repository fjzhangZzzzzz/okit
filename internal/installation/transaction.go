package installation

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

type TransactionState string

const (
	TransactionPrepared          TransactionState = "prepared"
	TransactionBackedUp          TransactionState = "backed_up"
	TransactionBinariesInstalled TransactionState = "binaries_installed"
	TransactionMetadataCommitted TransactionState = "metadata_committed"
	TransactionCompleted         TransactionState = "completed"
)

type UpdateTransaction struct {
	Schema         int              `json:"schema"`
	State          TransactionState `json:"state"`
	OKITHome       string           `json:"okit_home"`
	TransactionDir string           `json:"transaction_dir"`
	Current        string           `json:"current"`
	CurrentUpdater string           `json:"current_updater"`
	Staged         string           `json:"staged"`
	StagedUpdater  string           `json:"staged_updater"`
	Backup         string           `json:"backup"`
	UpdaterBackup  string           `json:"updater_backup"`
	StagedSHA256   string           `json:"staged_sha256"`
	UpdaterSHA256  string           `json:"updater_sha256"`
	OldMetadata    Metadata         `json:"old_metadata"`
	NewMetadata    Metadata         `json:"new_metadata"`
	WaitPID        int              `json:"wait_pid,omitempty"`
	ResultPath     string           `json:"result_path,omitempty"`
}
type TransactionResult struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func ReadTransactionResult(home string) (TransactionResult, error) {
	data, err := os.ReadFile(filepath.Join(home, "transactions", "result.json"))
	if err != nil {
		return TransactionResult{}, err
	}
	var result TransactionResult
	if err := json.Unmarshal(data, &result); err != nil {
		return TransactionResult{}, err
	}
	return result, nil
}

func transactionPath(home string) string { return filepath.Join(home, "transactions", "current.json") }
func TransactionPath(home string) string { return transactionPath(home) }

func SaveTransaction(t UpdateTransaction) error {
	if err := validateTransaction(t); err != nil {
		return err
	}
	dir := filepath.Dir(transactionPath(t.OKITHome))
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	data, err := json.Marshal(t)
	if err != nil {
		return err
	}
	tmp, err := os.CreateTemp(dir, ".transaction-*.tmp")
	if err != nil {
		return err
	}
	name := tmp.Name()
	defer os.Remove(name)
	if _, err = tmp.Write(data); err == nil {
		err = tmp.Sync()
	}
	if closeErr := tmp.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		return err
	}
	return os.Rename(name, transactionPath(t.OKITHome))
}

func LoadTransaction(home string) (UpdateTransaction, error) {
	data, err := os.ReadFile(transactionPath(home))
	if err != nil {
		return UpdateTransaction{}, err
	}
	var t UpdateTransaction
	if err := json.Unmarshal(data, &t); err != nil {
		return UpdateTransaction{}, err
	}
	if err := validateTransaction(t); err != nil {
		return UpdateTransaction{}, err
	}
	return t, nil
}

func validateTransaction(t UpdateTransaction) error {
	if t.Schema != 1 || t.OKITHome == "" || t.TransactionDir == "" {
		return errors.New("invalid update transaction")
	}
	for _, p := range []string{t.OKITHome, t.TransactionDir, t.Current, t.CurrentUpdater, t.Staged, t.StagedUpdater, t.Backup, t.UpdaterBackup} {
		if p == "" || !filepath.IsAbs(p) {
			return errors.New("update transaction contains unsafe path")
		}
		if p != filepath.Clean(t.OKITHome) && p != filepath.Clean(t.Current) && p != filepath.Clean(t.CurrentUpdater) && !pathWithin(t.OKITHome, p) {
			return errors.New("update transaction escapes OKIT_HOME")
		}
	}
	if filepath.Clean(t.TransactionDir) != filepath.Clean(filepath.Dir(t.Staged)) {
		return errors.New("staged files are outside transaction directory")
	}
	if filepath.Clean(t.Current) != filepath.Clean(t.NewMetadata.Executable) {
		return errors.New("transaction metadata executable mismatch")
	}
	if filepath.Dir(t.Current) != filepath.Dir(t.CurrentUpdater) {
		return errors.New("installed files are not paired")
	}
	if filepath.Base(t.Current) != "okit.exe" || filepath.Base(t.CurrentUpdater) != "okit-updater.exe" {
		return errors.New("unexpected managed file")
	}
	return nil
}

func pathWithin(root, target string) bool {
	r, err1 := filepath.Abs(root)
	p, err2 := filepath.Abs(target)
	if err1 != nil || err2 != nil {
		return false
	}
	rel, err := filepath.Rel(filepath.Clean(r), filepath.Clean(p))
	return err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator))
}

func fileSHA256(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func ApplyTransaction(t UpdateTransaction) error {
	if err := validateTransaction(t); err != nil {
		return err
	}
	if got, err := fileSHA256(t.Staged); err != nil || got != t.StagedSHA256 {
		return fmt.Errorf("staged executable checksum mismatch")
	}
	if got, err := fileSHA256(t.StagedUpdater); err != nil || got != t.UpdaterSHA256 {
		return fmt.Errorf("staged updater checksum mismatch")
	}
	t.State = TransactionPrepared
	if err := SaveTransaction(t); err != nil {
		return err
	}
	if err := os.Rename(t.Current, t.Backup); err != nil {
		return err
	}
	if err := os.Rename(t.CurrentUpdater, t.UpdaterBackup); err != nil {
		_ = os.Rename(t.Backup, t.Current)
		return err
	}
	t.State = TransactionBackedUp
	if err := SaveTransaction(t); err != nil {
		return err
	}
	if err := os.Rename(t.Staged, t.Current); err != nil {
		return rollbackTransaction(t, err)
	}
	if err := os.Rename(t.StagedUpdater, t.CurrentUpdater); err != nil {
		return rollbackTransaction(t, err)
	}
	t.State = TransactionBinariesInstalled
	if err := SaveTransaction(t); err != nil {
		return rollbackTransaction(t, err)
	}
	if err := SaveMetadata(t.OKITHome, t.NewMetadata); err != nil {
		return rollbackTransaction(t, err)
	}
	t.State = TransactionMetadataCommitted
	if err := SaveTransaction(t); err != nil {
		return err
	}
	_ = os.Remove(t.Backup)
	_ = os.Remove(t.UpdaterBackup)
	t.State = TransactionCompleted
	if err := SaveTransaction(t); err != nil {
		return err
	}
	return os.Remove(transactionPath(t.OKITHome))
}

func rollbackTransaction(t UpdateTransaction, cause error) error {
	if _, err := os.Stat(t.Backup); err == nil {
		_ = os.Remove(t.Current)
		_ = os.Rename(t.Backup, t.Current)
	}
	if _, err := os.Stat(t.UpdaterBackup); err == nil {
		_ = os.Remove(t.CurrentUpdater)
		_ = os.Rename(t.UpdaterBackup, t.CurrentUpdater)
	}
	_ = SaveMetadata(t.OKITHome, t.OldMetadata)
	return cause
}

func RecoverTransaction(home string) (bool, error) {
	t, err := LoadTransaction(home)
	if os.IsNotExist(err) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if t.State == TransactionMetadataCommitted || t.State == TransactionCompleted {
		_ = os.Remove(transactionPath(home))
		return true, nil
	}
	if t.State == TransactionPrepared {
		if _, statErr := os.Stat(t.Backup); os.IsNotExist(statErr) {
			return false, errors.New("update transaction was not backed up; refusing destructive recovery")
		}
	}
	_ = rollbackTransaction(t, errors.New("recovering interrupted update"))
	if _, err := os.Stat(t.Current); err != nil {
		return false, fmt.Errorf("recovery could not restore executable: %w", err)
	}
	_ = os.Remove(transactionPath(home))
	return true, nil
}
