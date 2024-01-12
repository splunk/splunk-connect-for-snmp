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
