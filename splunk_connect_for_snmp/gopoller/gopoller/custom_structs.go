package gopoller

type Pdu struct {
	Value string
	Name  string
	Type  string
}

type OidSlice []string

type SnmpV3StringAuthData struct {
	UserName                 string
	AuthenticationProtocol   string
	AuthenticationPassphrase string
	PrivacyProtocol          string
	PrivacyPassphrase        string
	AuthoritativeEngineID    string
}

type WalkConfiguration struct {
	UserName                 string   `json:"userName"`
	AuthenticationProtocol   string   `json:"authenticationProtocol"`
	AuthenticationPassphrase string   `json:"authenticationPassphrase"`
	PrivacyProtocol          string   `json:"privacyProtocol"`
	PrivacyPassphrase        string   `json:"privacyPassphrase"`
	AuthoritativeEngineID    string   `json:"authoritativeEngineID"`
	Target                   string   `json:"target"`
	Port                     int      `json:"port"`
	Community                string   `json:"community"`
	Oids                     []string `json:"oids"`
	IgnoreNonIncreasingOid   bool     `json:"ignoreNonIncreasingOid"`
	Version                  string   `json:"version"`
}

type WalkResults struct {
	PduList []Pdu `json:"pduList"`
}
