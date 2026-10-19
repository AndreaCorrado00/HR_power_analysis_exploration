# Studio locale HR / Power

Webapp Vue locale per atleti, storico FIT, identificazione esplicita, modelli
versionati, prescrizioni e confronto prospettico. Lo studio precedente è in
[`archive/`](archive/README_ARCHIVE.md).

Da PowerShell nella radice:

```powershell
.\study_app\start.ps1
```

Aprire <http://127.0.0.1:8770>. Al primo setup su un nuovo checkout:

```powershell
.\study_app\start.ps1 -Setup
```

Il nuovo storage parte vuoto. Importazione, preparazione e avvio non eseguono
fitting. Il primo fitting è riservato all'utente tramite **Avvia identificazione**.
Le previsioni HR non calibrano B o HR0 sui dati validation.

- [Guida e limiti](study_app/README.md)
- [Specifica](planning/local-study-webapp/SPEC.md)
- [Piano e perimetro](planning/local-study-webapp/CONTROL.md)
- [Verifiche effettuate](planning/local-study-webapp/VERIFICATION.md)
