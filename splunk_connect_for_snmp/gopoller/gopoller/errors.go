package gopoller

import "fmt"

type SnmpError struct {
	message string
}

func (e *SnmpError) Error() string {
	return fmt.Sprintf(e.message)
}
