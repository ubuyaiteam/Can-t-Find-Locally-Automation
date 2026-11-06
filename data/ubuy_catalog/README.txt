Drop one catalogue file per Ubuy store here, named by country code:
   IN.tsv   NG.csv   AE.xml   ...
Accepted formats: Google Merchant Center feed export (TSV/CSV with a 'title' column; 'link', 'price', 'availability' optional)
or the Merchant Center XML/RSS feed (<item><title>, <g:link>, <g:price>, <g:availability>).
The engine uses it to tell "already in the Ubuy catalogue -> launch campaign now" from "not in catalogue -> add SKU".
Without a file the Ubuy column shows "Not checked" - products are NOT rejected because of it.
