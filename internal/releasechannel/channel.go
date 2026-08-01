// Package releasechannel owns the rules for locating release channel pointers.
package releasechannel

import "strings"

const PrereleasePointer = "pre-release"

type Request struct {
	Version           string
	IncludePrerelease bool
}

func ManifestPath(request Request) string {
	if request.Version != "" {
		return "/download/" + request.Version + "/release-manifest.json"
	}
	if request.IncludePrerelease {
		return "/download/" + PrereleasePointer + "/release-manifest.json"
	}
	return "/latest/download/release-manifest.json"
}

// CanAdvancePrerelease prevents publishing a pointer before its manifest is verified.
func CanAdvancePrerelease(manifestVerified bool) bool { return manifestVerified }

func Join(base string, request Request) string {
	return strings.TrimRight(base, "/") + ManifestPath(request)
}
