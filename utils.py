def parse_date(date):
    date_string = str(date)
    date_string = date_string.replace('T', ' ')
    date_string = date_string.split('.', 1)[0]
    if date_string is None:
        return "0"
    
    return date_string

def parse_unicode(text):
    if isinstance(text, unicode):
        return text.encode('utf8', 'replace')

    return str(text)
