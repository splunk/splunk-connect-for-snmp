package gopoller

import (
	"fmt"
	"github.com/gosnmp/gosnmp"
	"log"
	"os"
	"time"
)

func getVersion(version string) (gosnmp.SnmpVersion, error) {
	switch version {
	case "1":
		return gosnmp.Version1, nil
	case "2c":
		return gosnmp.Version2c, nil
	case "3":
		return gosnmp.Version3, nil
	default:
		return gosnmp.Version1, &SnmpError{fmt.Sprintf("%s is not a valid snmp version", version)}
	}
}

func getAuthProtocol(authProtocol string) (gosnmp.SnmpV3AuthProtocol, error) {
	// According to documentation (https://pkg.go.dev/github.com/gosnmp/gosnmp@v1.37.0#SnmpV3AuthProtocol)
	// currently only NoAuth, MD5, and SHA are implemented
	switch authProtocol {
	case "NoAuth":
		return gosnmp.NoAuth, nil
	case "MD5":
		return gosnmp.MD5, nil
	case "SHA":
		return gosnmp.SHA, nil
	default:
		return 0, &SnmpError{fmt.Sprintf("%s authentication protocol is not implemented", authProtocol)}
	}
}

func getPrivacyProtocol(privacyProtocol string) (gosnmp.SnmpV3PrivProtocol, error) {
	switch privacyProtocol {
	case "NoPriv":
		return gosnmp.NoPriv, nil
	case "DES":
		return gosnmp.DES, nil
	case "AES":
		return gosnmp.AES, nil
	case "AES192":
		return gosnmp.AES192, nil
	case "AES256":
		return gosnmp.AES256, nil
	case "AES192C":
		return gosnmp.AES192C, nil
	case "AES256C":
		return gosnmp.AES256C, nil
	default:
		return 0, &SnmpError{fmt.Sprintf("%s privacy protocol is not implemented", privacyProtocol)}
	}
}

func getSecurityParameters(authData SnmpV3StringAuthData) (*gosnmp.UsmSecurityParameters, error) {
	var result gosnmp.UsmSecurityParameters
	authProtocol, err := getAuthProtocol(authData.AuthenticationProtocol)
	if err != nil {
		return nil, err
	}

	privProtocol, err := getPrivacyProtocol(authData.PrivacyProtocol)
	if err != nil {
		return nil, err
	}

	result = gosnmp.UsmSecurityParameters{
		UserName:                 authData.UserName,
		AuthenticationProtocol:   authProtocol,
		AuthenticationPassphrase: authData.AuthenticationPassphrase,
		PrivacyProtocol:          privProtocol,
		PrivacyPassphrase:        authData.PrivacyPassphrase,
		AuthoritativeEngineID:    authData.AuthoritativeEngineID,
	}
	useLogger := os.Getenv("ENABLE_GO_LOGGER")
	if humanBool(useLogger, false) {
		result.Logger = gosnmp.NewLogger(log.New(os.Stdout, "", 0))
	}
	return &result, nil
}

func getGoSnmp(target string, port int, ignoreNonIncreasingOid bool, version string, community string,
	authData SnmpV3StringAuthData, timeoutSeconds int) (*gosnmp.GoSNMP, error) {
	snmpVersion, err := getVersion(version)

	if err != nil {
		return nil, err
	}

	var result gosnmp.GoSNMP
	var appOpts = map[string]interface{}{"c": !ignoreNonIncreasingOid}

	if snmpVersion != gosnmp.Version3 {
		result = gosnmp.GoSNMP{
			Target:             target,
			Port:               uint16(port),
			Transport:          "udp",
			ContextEngineID:    "", //defined in contextData, in Go only for v3
			ContextName:        "", //defined in contextData, in Go only for v3
			MaxRepetitions:     1,
			NonRepeaters:       10,
			AppOpts:            appOpts, //set AppOpts to c if ignoreNonIncreasingOid=false, no c if ignoreNonIncreasingOid=true
			Community:          community,
			Version:            snmpVersion,                                 // have to set to correct version and add necessary params for v3
			Timeout:            time.Duration(timeoutSeconds) * time.Second, // timeout of one request/response, possibly not the updconnectiontimeout??
			ExponentialTimeout: true,
		}
	} else {
		securityParameters, err := getSecurityParameters(authData)
		if err != nil {
			return nil, err
		}
		result = gosnmp.GoSNMP{
			Target:             target,
			Port:               uint16(port),
			Transport:          "udp",
			ContextEngineID:    "", //defined in contextData, in Go only for v3
			ContextName:        "", //defined in contextData, in Go only for v3
			MaxRepetitions:     1,
			NonRepeaters:       10,
			AppOpts:            appOpts, //set AppOpts to c if ignoreNonIncreasingOid=false, no c if ignoreNonIncreasingOid=true
			Version:            snmpVersion,
			SecurityModel:      gosnmp.UserSecurityModel,
			MsgFlags:           gosnmp.AuthPriv,
			Timeout:            time.Duration(timeoutSeconds) * time.Second,
			ExponentialTimeout: true,
			SecurityParameters: securityParameters,
		}
	}

	useLogger := os.Getenv("ENABLE_GO_LOGGER")
	if humanBool(useLogger, false) {
		result.Logger = gosnmp.NewLogger(log.New(os.Stdout, "", 0))
	}

	return &result, nil
}
