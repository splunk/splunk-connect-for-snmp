package gopoller

//package main

import (
	"fmt"
	"github.com/gosnmp/gosnmp"
	"time"
)

type Pdu struct {
	Value string
	Name  string
	Type  string
}

func PerformBulkWalk(authData string, target string, community string, oid string, port int, ignoreNonIncreasingOid bool, version string) ([]Pdu, error) {
	var appOpts = map[string]interface{}{"c": !ignoreNonIncreasingOid}

	params := &gosnmp.GoSNMP{
		Target:             target,
		Port:               uint16(port),
		Transport:          "udp",
		ContextEngineID:    "", //defined in contextData, in Go only for v3
		ContextName:        "", //defined in contextData, in Go only for v3
		MaxRepetitions:     1,
		NonRepeaters:       10,
		AppOpts:            appOpts, //set AppOpts to c if ignoreNonIncreasingOid=false, no c if ignoreNonIncreasingOid=true
		Community:          community,
		Version:            getVersion(version),               // have to set to correct version and add necessary params for v3
		Timeout:            time.Duration(1800) * time.Second, // timeout of one request/response, possibly not the updconnectiontimeout??
		ExponentialTimeout: true,
		//Logger:             gosnmp.NewLogger(log.New(os.Stdout, "", 0)), //for now logging to stdout for debuging
	}

	err := params.Connect()
	if err != nil {
		return nil, fmt.Errorf("error connecting to %s: %v", target, err)
	}
	defer params.Conn.Close()

	//call for specific oid
	res, err := params.BulkWalkAll(oid)
	if err != nil {
		return nil, fmt.Errorf("walk Error: %v", err)
	}

	//parse response to Pdu struct, so it could be translated by gopy and return to python
	var pdus []Pdu
	for _, snmppdu := range res {
		pdu := Pdu{ToString(snmppdu.Value, snmppdu.Type),
			snmppdu.Name,
			snmppdu.Type.String(),
		}
		pdus = append(pdus, pdu)
	}

	return pdus, nil
}

func ToString(value interface{}, vtype gosnmp.Asn1BER) string {
	// Parse any Asn1BER type to string
	switch vtype {
	case gosnmp.OctetString:
		bytes := value.([]byte)
		return fmt.Sprintf("%s", string(bytes))
	default:
		return fmt.Sprintf("%v", value)
	}
}

func getVersion(version string) gosnmp.SnmpVersion {
	switch version {
	case "1":
		return gosnmp.Version1
	case "2c":
		return gosnmp.Version2c
	default:
		return gosnmp.Version3
	}
}

// Left for testing in go
//func main() {
//	start := time.Now()
//	res, err := PerformBulkWalk("xd", "54.91.99.113", "public", "1.3.6.1.2.1.31", 161, false, "2c")
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
