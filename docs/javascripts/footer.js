function legalFooter() {
    let copyright = document.createElement('div');
    copyright.classList.add('md-copyright__highlight');
    let content = document.createElement('p');
    content.style.textAlign = 'center';
    let termsLink = document.createElement('a');
    termsLink.href = 'https://github.com/splunk/splunk-connect-for-snmp/blob/main/LICENSE';
    termsLink.innerHTML = 'Apache 2.0';
    content.append('Splunk Documentation covered by: ');
    content.append(termsLink);

    let endElement = document.getElementsByTagName('main')[0];
    endElement.insertAdjacentElement("afterend", content);
}

legalFooter()