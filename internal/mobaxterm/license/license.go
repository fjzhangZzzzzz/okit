package license

import (
	"archive/zip"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"unicode/utf8"
)

const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="

type Info struct {
	Username    string `json:"username"`
	Version     string `json:"version"`
	LicenseType string `json:"license_type"`
	UserCount   int    `json:"user_count"`
	Key         string `json:"license_key"`
	Decoded     string `json:"decoded_string"`
}

func Generate(username, version string) (string, error) {
	if strings.TrimSpace(username) == "" || strings.ContainsAny(username, "#|\r\n") {
		return "", errors.New("username is empty or contains a reserved character")
	}
	major, minor, err := normalizeVersion(version)
	if err != nil {
		return "", err
	}
	plain := fmt.Sprintf("1#%s|%d%d#1#%d3%d6%d#0#0#0#", username, major, minor, major, minor, minor)
	encrypted := cryptEncrypt(0x787, []byte(plain))
	return variantEncode(encrypted), nil
}

func normalizeVersion(version string) (int, int, error) {
	parts := strings.Split(strings.TrimSpace(version), ".")
	if len(parts) == 0 || parts[0] == "" {
		return 0, 0, errors.New("version is empty")
	}
	major, err := strconv.Atoi(parts[0])
	if err != nil || major < 0 {
		return 0, 0, fmt.Errorf("invalid major version %q", parts[0])
	}
	minor := 0
	if len(parts) >= 2 {
		minor, err = strconv.Atoi(parts[1])
		if err != nil || minor < 0 || minor > 9 {
			return 0, 0, fmt.Errorf("invalid minor version %q", parts[1])
		}
	}
	return major, minor, nil
}

func variantEncode(input []byte) string {
	var result strings.Builder
	for i := 0; i < len(input); i += 3 {
		count := min(3, len(input)-i)
		var value uint32
		for j := 0; j < count; j++ {
			value |= uint32(input[i+j]) << (8 * j)
		}
		for j := 0; j < count+1; j++ {
			result.WriteByte(alphabet[(value>>uint(6*j))&0x3f])
		}
	}
	return result.String()
}

func variantDecode(input string) ([]byte, error) {
	if len(input)%4 == 1 {
		return nil, errors.New("invalid variant base64 length")
	}
	reverse := make(map[byte]uint32, len(alphabet))
	for i := 0; i < len(alphabet); i++ {
		reverse[alphabet[i]] = uint32(i)
	}
	result := make([]byte, 0, len(input)*3/4)
	for i := 0; i < len(input); {
		count := min(4, len(input)-i)
		if count < 2 {
			return nil, errors.New("invalid variant base64 block")
		}
		var value uint32
		for j := 0; j < count; j++ {
			decoded, ok := reverse[input[i+j]]
			if !ok || decoded >= 64 {
				return nil, fmt.Errorf("invalid variant base64 character %q", input[i+j])
			}
			value |= decoded << uint(6*j)
		}
		byteCount := count - 1
		buffer := make([]byte, 4)
		binary.LittleEndian.PutUint32(buffer, value)
		result = append(result, buffer[:byteCount]...)
		i += count
	}
	return result, nil
}

func cryptEncrypt(key int, input []byte) []byte {
	result := make([]byte, len(input))
	for i, value := range input {
		result[i] = value ^ byte((key>>8)&0xff)
		key = int(result[i])&key | 0x482D
	}
	return result
}

func cryptDecrypt(key int, input []byte) []byte {
	result := make([]byte, len(input))
	for i, value := range input {
		result[i] = value ^ byte((key>>8)&0xff)
		key = int(value)&key | 0x482D
	}
	return result
}

func Decode(key string) (string, error) {
	encrypted, err := variantDecode(strings.TrimSpace(key))
	if err != nil {
		return "", err
	}
	plain := cryptDecrypt(0x787, encrypted)
	if !utf8.Valid(plain) {
		return "", errors.New("license content is not valid UTF-8")
	}
	return string(plain), nil
}

func InspectKey(key string) (Info, error) {
	decoded, err := Decode(key)
	if err != nil {
		return Info{}, err
	}
	parts := strings.Split(decoded, "#")
	if len(parts) < 7 || !strings.Contains(parts[1], "|") {
		return Info{}, errors.New("invalid license structure")
	}
	usernameVersion := strings.SplitN(parts[1], "|", 2)
	versionPart := usernameVersion[1]
	version := versionPart
	if len(versionPart) == 3 {
		version = versionPart[:2] + "." + versionPart[2:]
	} else if len(versionPart) == 2 {
		version = versionPart + ".0"
	}
	count, err := strconv.Atoi(parts[2])
	if err != nil || count < 0 {
		return Info{}, errors.New("invalid license user count")
	}
	licenseType := map[string]string{"1": "Professional", "3": "Educational", "4": "Personal"}[parts[0]]
	if licenseType == "" {
		licenseType = "Type " + parts[0]
	}
	return Info{Username: usernameVersion[0], Version: version, LicenseType: licenseType, UserCount: count, Key: key, Decoded: decoded}, nil
}

func Verify(key, username, version string) (bool, error) {
	info, err := InspectKey(key)
	if err != nil {
		return false, err
	}
	major, minor, err := normalizeVersion(version)
	if err != nil {
		return false, err
	}
	wantVersion := fmt.Sprintf("%d.%d", major, minor)
	return info.Username == username && info.Version == wantVersion && info.LicenseType == "Professional", nil
}

func CreateFile(path, key string) error {
	if _, err := InspectKey(key); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), ".license-*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	writer := zip.NewWriter(tmp)
	entry, err := writer.Create("Pro.key")
	if err == nil {
		_, err = io.WriteString(entry, key)
	}
	if closeErr := writer.Close(); err == nil {
		err = closeErr
	}
	if syncErr := tmp.Sync(); err == nil {
		err = syncErr
	}
	if closeErr := tmp.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		return err
	}
	swap := path + ".okit-swap"
	_ = os.Remove(swap)
	hadOriginal := false
	if _, statErr := os.Stat(path); statErr == nil {
		if err := os.Rename(path, swap); err != nil {
			return err
		}
		hadOriginal = true
	} else if !os.IsNotExist(statErr) {
		return statErr
	}
	if err := os.Rename(tmpName, path); err != nil {
		if hadOriginal {
			_ = os.Rename(swap, path)
		}
		return err
	}
	if hadOriginal {
		return os.Remove(swap)
	}
	return nil
}

func ReadFile(path string) (string, error) {
	reader, err := zip.OpenReader(path)
	if err != nil {
		return "", err
	}
	defer reader.Close()
	for _, file := range reader.File {
		if file.Name != "Pro.key" {
			continue
		}
		stream, err := file.Open()
		if err != nil {
			return "", err
		}
		data, err := io.ReadAll(io.LimitReader(stream, 1<<20))
		stream.Close()
		if err != nil {
			return "", err
		}
		key := strings.TrimSpace(string(data))
		if _, err := InspectKey(key); err != nil {
			return "", err
		}
		return key, nil
	}
	return "", errors.New("Pro.key is missing from license file")
}
