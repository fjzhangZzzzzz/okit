package selfmanage

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
)

var ErrNoUpdate = errors.New("no update available")

type semanticVersion struct {
	major, minor, patch int
	prerelease          string
}

func parseVersion(value string) (semanticVersion, error) {
	value = strings.TrimPrefix(strings.TrimSpace(value), "v")
	parts := strings.SplitN(value, "-", 2)
	numbers := strings.Split(parts[0], ".")
	if len(numbers) != 3 {
		return semanticVersion{}, fmt.Errorf("invalid semantic version %q", value)
	}
	parsed := semanticVersion{}
	values := []*int{&parsed.major, &parsed.minor, &parsed.patch}
	for i, number := range numbers {
		converted, err := strconv.Atoi(number)
		if err != nil || converted < 0 {
			return semanticVersion{}, fmt.Errorf("invalid semantic version %q", value)
		}
		*values[i] = converted
	}
	if len(parts) == 2 {
		parsed.prerelease = parts[1]
		if parsed.prerelease == "" {
			return semanticVersion{}, fmt.Errorf("invalid semantic version %q", value)
		}
	}
	return parsed, nil
}

func compareVersion(left, right semanticVersion) int {
	for _, pair := range [][2]int{{left.major, right.major}, {left.minor, right.minor}, {left.patch, right.patch}} {
		if pair[0] < pair[1] {
			return -1
		}
		if pair[0] > pair[1] {
			return 1
		}
	}
	if left.prerelease == right.prerelease {
		return 0
	}
	if left.prerelease == "" {
		return 1
	}
	if right.prerelease == "" {
		return -1
	}
	leftParts := strings.Split(left.prerelease, ".")
	rightParts := strings.Split(right.prerelease, ".")
	for index := 0; index < len(leftParts) && index < len(rightParts); index++ {
		if leftParts[index] == rightParts[index] {
			continue
		}
		leftNumber, leftErr := strconv.Atoi(leftParts[index])
		rightNumber, rightErr := strconv.Atoi(rightParts[index])
		if leftErr == nil && rightErr == nil {
			if leftNumber < rightNumber {
				return -1
			}
			if leftNumber > rightNumber {
				return 1
			}
			continue
		}
		if leftErr == nil {
			return -1
		}
		if rightErr == nil {
			return 1
		}
		if leftParts[index] < rightParts[index] {
			return -1
		}
		return 1
	}
	if len(leftParts) < len(rightParts) {
		return -1
	}
	if len(leftParts) == len(rightParts) {
		return 0
	}
	return 1
}

func SelectRelease(current string, releases []Release, options UpdateOptions) (Release, error) {
	currentVersion, err := parseVersion(current)
	if err != nil {
		return Release{}, err
	}
	if options.Version != "" {
		for _, release := range releases {
			if strings.TrimPrefix(release.Version, "v") == strings.TrimPrefix(options.Version, "v") {
				return release, nil
			}
		}
		return Release{}, fmt.Errorf("release %s was not found", options.Version)
	}
	var selected Release
	var selectedVersion semanticVersion
	for _, release := range releases {
		if release.Prerelease && !options.Prerelease {
			continue
		}
		parsed, err := parseVersion(release.Version)
		if err != nil {
			continue
		}
		if selected.Version == "" || compareVersion(parsed, selectedVersion) > 0 {
			selected, selectedVersion = release, parsed
		}
	}
	if selected.Version == "" {
		return Release{}, errors.New("no matching release was found")
	}
	if compareVersion(selectedVersion, currentVersion) <= 0 {
		return Release{}, fmt.Errorf("%w (current %s)", ErrNoUpdate, current)
	}
	return selected, nil
}
