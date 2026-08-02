//go:build !windows

package installation

import "os"

func PlatformReplace(executable, staged string) (bool, error) {
	return false, CompleteReplacement(executable, staged, os.Rename)
}

func PlatformReplaceTransaction(t UpdateTransaction) (bool, error) {
	return false, ApplyTransaction(t)
}

func NativeTransactionReplace() TransactionReplaceFunc { return nil }
