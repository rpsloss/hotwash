# cases

Portable traces plus expect files. Vendor logs are not stored here.

```bash
python3 -m hotwash --eval cases
```

Add a case by freezing a real session:

```bash
python3 -m hotwash path/to/session --write-case cases/short-name
```
