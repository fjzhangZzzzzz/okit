//go:build windows

package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/fjzhangZzzzzz/okit/internal/installation"
	"golang.org/x/sys/windows"
)

func main() {
	jobPath := flag.String("job", "", "更新任务文件")
	uninstallJobPath := flag.String("uninstall-job", "", "卸载任务文件")
	flag.Parse()
	if *jobPath == "" && *uninstallJobPath == "" {
		os.Exit(2)
	}
	if *uninstallJobPath != "" {
		runUninstall(*uninstallJobPath)
		return
	}
	job, err := installation.LoadUpdateJob(*jobPath)
	if err == nil && job.WaitPID > 0 {
		var handle windows.Handle
		handle, err = windows.OpenProcess(windows.SYNCHRONIZE, false, uint32(job.WaitPID))
		if err == nil {
			_, err = windows.WaitForSingleObject(handle, windows.INFINITE)
			windows.CloseHandle(handle)
		}
	}
	if err == nil {
		err = installation.ApplyUpdateJob(job)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func runUninstall(path string) {
	job, err := installation.LoadUninstallJob(path)
	if err == nil && job.WaitPID > 0 {
		handle, openErr := windows.OpenProcess(windows.SYNCHRONIZE, false, uint32(job.WaitPID))
		if openErr != nil {
			err = openErr
		} else {
			_, err = windows.WaitForSingleObject(handle, windows.INFINITE)
			windows.CloseHandle(handle)
		}
	}
	if err == nil {
		err = installation.ApplyUninstallJob(job)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
