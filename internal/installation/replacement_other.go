//go:build !windows

package installation

import "os"

func PlatformReplace(executable, staged string) (bool, error) {
	return false, CompleteReplacement(executable, staged, os.Rename)
}
