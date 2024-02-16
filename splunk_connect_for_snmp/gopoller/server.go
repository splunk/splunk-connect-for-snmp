package main

import (
	"encoding/json"
	"fmt"
	"gopoller/gopoller"
	"log"
	"net/http"
	"time"
)

func handleWalk(rw http.ResponseWriter, r *http.Request) {
	if r.Method == "POST" {
		var walkConfig gopoller.WalkConfiguration
		err := json.NewDecoder(r.Body).Decode(&walkConfig)
		if err != nil {
			rw.WriteHeader(400)
			_, err1 := rw.Write([]byte(fmt.Sprintf("Problem with decoding json: %s", err)))
			if err1 != nil {
				return
			}
		}

		authData := gopoller.SnmpV3StringAuthData{
			UserName:                 walkConfig.UserName,
			AuthenticationProtocol:   walkConfig.AuthenticationProtocol,
			AuthenticationPassphrase: walkConfig.AuthenticationPassphrase,
			PrivacyProtocol:          walkConfig.PrivacyProtocol,
			PrivacyPassphrase:        walkConfig.PrivacyPassphrase,
			AuthoritativeEngineID:    walkConfig.AuthoritativeEngineID,
		}
		log.Print("Starting walk")
		pduList, err := gopoller.PerformBulkWalk(authData, walkConfig.Target, walkConfig.Community, walkConfig.Oids,
			walkConfig.Port, walkConfig.IgnoreNonIncreasingOid, walkConfig.Version)
		if err != nil {
			rw.WriteHeader(400)
			_, err1 := rw.Write([]byte(fmt.Sprintf("While performing bulk walk, error occured: %s", err)))
			if err1 != nil {
				return
			}
		} else {
			result := gopoller.WalkResults{PduList: pduList}
			err1 := json.NewEncoder(rw).Encode(result)
			if err1 != nil {
				rw.WriteHeader(400)
			}
		}
	}
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/walk", handleWalk)
	s := &http.Server{
		Addr:         ":9000",
		Handler:      mux,
		ReadTimeout:  0 * time.Second,
		WriteTimeout: 0 * time.Second,
		IdleTimeout:  0 * time.Second,
	}
	log.Fatal(s.ListenAndServe())
}

//func main() {
//	start := time.Now()
//	//oids := OidSlice{"1.3.6.1.2.1.31"}
//	//res, err := PerformBulkWalk(SnmpV3StringAuthData{}, "54.91.99.113", "public", oids, 161, false, "2c")
//	//res, err := PerformGet(SnmpV3StringAuthData{}, "54.91.99.113", "public", OidSlice{"1.3.6.1.2.1.1.6.0"}, 161, false, "2c")
//
//	// TEST VERSION 3
//	var authData = gopoller.SnmpV3StringAuthData{
//		UserName:                 "r-wuser",
//		PrivacyProtocol:          "AES",
//		PrivacyPassphrase:        "admin1234",
//		AuthenticationProtocol:   "SHA",
//		AuthenticationPassphrase: "admin1234",
//		AuthoritativeEngineID:    "",
//	}
//	//oids := []string{"1.3.6.1.2.1.1"}
//	oids := []string{"1.3.6.1.2.1.4"}
//	res, err := gopoller.PerformBulkWalk(authData, "3.22.240.75", "public", oids, 161, false, "3")
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
