package gopoller

//package main

import (
	"encoding/hex"
	"fmt"
	"github.com/gosnmp/gosnmp"
	"strconv"
	"strings"
)

func PerformBulkWalk(authData SnmpV3StringAuthData, target string, community string, oids []string, port int, ignoreNonIncreasingOid bool, version string) ([]Pdu, error) {
	params, err := getGoSnmp(target, port, ignoreNonIncreasingOid, version, community, authData, 3)

	if err != nil {
		return nil, fmt.Errorf("an error occured while creating gosnmp.GoSNMP:  %v", err)
	}

	params.Logger.Print("Hello from GO")
	params.Logger.Printf("%v", params)
	err = params.Connect()
	if err != nil {
		return nil, fmt.Errorf("error connecting to %s: %v", target, err)
	}
	defer params.Conn.Close()

	//call for specific oid
	var pdus []Pdu
	for _, oid := range oids {
		res, err := params.BulkWalkAll(oid)
		if err != nil {
			return nil, fmt.Errorf("an error occured during snmp walk: %v", err)
		}
		for _, snmppdu := range res {
			pdu := Pdu{ToString(snmppdu.Value, snmppdu.Type),
				snmppdu.Name,
				snmppdu.Type.String(),
			}
			pdus = append(pdus, pdu)
		}
	}

	//parse response to Pdu struct, so it could be translated by gopy and return to python
	return pdus, nil
}

func ToString(value interface{}, vtype gosnmp.Asn1BER) string {
	// Parse any Asn1BER type to string
	switch vtype {
	case gosnmp.OctetString:
		bytes := value.([]byte)
		if strings.Contains(strconv.Quote(string(bytes)), "\\x") {
			return hex.EncodeToString(bytes)
		}
		return fmt.Sprintf("%s", string(bytes))
	default:
		return fmt.Sprintf("%v", value)
	}
}

func PerformGet(authData SnmpV3StringAuthData, target string, community string, oids OidSlice, port int, ignoreNonIncreasingOid bool, version string) ([]Pdu, error) {
	params, err := getGoSnmp(target, port, ignoreNonIncreasingOid, version, community, authData, 3)
	if err != nil {
		return nil, fmt.Errorf("an error occured while creating gosnmp.GoSNMP:  %v", err)
	}

	err = params.Connect()
	if err != nil {
		return nil, fmt.Errorf("error connecting to %s: %v", target, err)
	}
	defer params.Conn.Close()

	res, err := params.Get(oids)
	if err != nil {
		return nil, fmt.Errorf("an error occured during snmp get: %v", err)
	}

	var pdus []Pdu
	for _, snmppdu := range res.Variables {
		pdu := Pdu{ToString(snmppdu.Value, snmppdu.Type),
			snmppdu.Name,
			snmppdu.Type.String(),
		}
		pdus = append(pdus, pdu)
	}

	return pdus, nil
}

// Left for testing in go
//func main() {
//	start := time.Now()
//	//oids := OidSlice{"1.3.6.1.2.1.31"}
//	//res, err := PerformBulkWalk(SnmpV3StringAuthData{}, "54.91.99.113", "public", oids, 161, false, "2c")
//	//res, err := PerformGet(SnmpV3StringAuthData{}, "54.91.99.113", "public", OidSlice{"1.3.6.1.2.1.1.6.0"}, 161, false, "2c")
//
//	// TEST VERSION 3
//	var authData = SnmpV3StringAuthData{
//		UserName:                 "r-wuser",
//		PrivacyProtocol:          "AES",
//		PrivacyPassphrase:        "admin1234",
//		AuthenticationProtocol:   "SHA",
//		AuthenticationPassphrase: "admin1234",
//		AuthoritativeEngineID:    "",
//	}
//	oids := OidSlice{"1.3.6.1.2.1.1"}
//	res, err := PerformBulkWalk(authData, "3.138.204.11", "public", oids, 161, false, "3")
//	//res, err := PerformGet(authData, "3.138.204.11", "public", OidSlice{"1.3.6.1.2.1.1.6.0"}, 161, false, "3")
//	elapsed := time.Since(start)
//
//	if err != nil {
//		fmt.Printf("%s \n", err)
//	}
//
//	for _, variable := range res {
//		fmt.Printf("%s -> %s: %v \n", variable.Name, variable.Type, variable.Value)
//	}
//
//	fmt.Printf("took %s \n", elapsed)
//}
