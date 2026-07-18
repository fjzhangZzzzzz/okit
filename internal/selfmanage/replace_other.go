//go:build !windows

package selfmanage

import "os"

func PlatformReplace(executable, staged string) (bool, error) {
	return false, CompleteReplacement(executable, staged, os.Rename)
}
