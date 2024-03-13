package gopoller

import "strings"

func humanBool(stringValue string, defaultValue bool) bool {
	stringValue = strings.ToLower(stringValue)
	if stringValue == "true" ||
		stringValue == "1" ||
		stringValue == "t" ||
		stringValue == "yes" ||
		stringValue == "y" {
		return true
	} else if stringValue == "false" ||
		stringValue == "0" ||
		stringValue == "f" ||
		stringValue == "no" ||
		stringValue == "n" {
		return false
	} else {
		return defaultValue
	}
}
