//go:build !windows

package installation

import "os"

func PlatformReplace(executable, staged, _ string, _ Metadata) (bool, error) {
	return false, CompleteReplacement(executable, staged, os.Rename)
}
