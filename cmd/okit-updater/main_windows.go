//go:build windows

package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"

	"github.com/fjzhangZzzzzz/okit/internal/installation"
	"golang.org/x/sys/windows"
)

type result struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func main() {
	if len(os.Args) != 3 || (os.Args[1] != "--transaction" && os.Args[1] != "--uninstall") {
		os.Exit(2)
	}
	if os.Args[1] == "--uninstall" {
		runUninstall(os.Args[2])
		return
	}
	tx, err := installation.LoadTransaction(filepath.Dir(filepath.Dir(os.Args[2])))
	if err == nil && tx.WaitPID > 0 {
		err = waitForProcess(tx.WaitPID)
	}
	if err == nil {
		err = installation.ApplyTransaction(tx)
	}
	if err != nil {
		_ = writeResult(os.Args[2], result{Code: "SELF_UPDATE_FAILED", Message: err.Error()})
		os.Exit(1)
	}
}

func runUninstall(path string) {
	job, err := installation.ReadUninstallJob(path)
	if err == nil {
		err = validateUninstallJob(path, job)
	}
	if err == nil && job.WaitPID > 0 {
		err = waitForProcess(job.WaitPID)
	}
	if err == nil {
		err = installation.ExecuteUninstallJob(job)
	}
	if err != nil {
		_ = writeResult(path, result{Code: "UNINSTALL_FAILED", Message: err.Error()})
		os.Exit(1)
	}
}

func validateUninstallJob(jobPath string, job installation.UninstallJob) error {
	return installation.ValidateUninstallJob(jobPath, job)
}

func waitForProcess(pid int) error {
	h, err := windows.OpenProcess(windows.SYNCHRONIZE, false, uint32(pid))
	if err != nil {
		if err == windows.ERROR_INVALID_PARAMETER {
			return nil
		}
		return err
	}
	defer windows.CloseHandle(h)
	_, err = windows.WaitForSingleObject(h, windows.INFINITE)
	return err
}

func writeResult(transactionFile string, r result) error {
	data, err := json.Marshal(r)
	if err != nil {
		return err
	}
	path := filepath.Join(filepath.Dir(transactionFile), "result.json")
	tmp := path + "." + strconv.FormatInt(int64(os.Getpid()), 10) + ".tmp"
	if err := os.WriteFile(tmp, data, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}
