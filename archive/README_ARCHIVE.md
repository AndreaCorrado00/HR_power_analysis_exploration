# Studio storico archiviato

Snapshot iniziale 0e0b365. Verificati 20135 file, 1486897092 byte.
Modelli congelati dell?esperimento prescribed_joint: potenza ordine 2 + AR(2), HR P1D/REML. Nessuna ristima.

Il manifest locale in planning/local-study-webapp/archive_manifest.local.json registra percorsi e hash. I link assoluti sono preservati: i loro target originali possono non risolversi dopo lo spostamento. La mappa source/destination nel manifest permette di ritrovare i raw. Il builder storico dipende anche dal checkout .worktrees, lasciato intatto. Non si dichiara questo archivio autosufficiente n? i vecchi launcher immediatamente avviabili.

Rollback: a servizio fermo, verificare tutti gli hash e i link del manifest, accertare assenza di collisioni alle sorgenti originali, quindi spostare solo move_roots dalla radice archive alla radice repository con Move-Item -LiteralPath. Se esiste un omonimo, fermarsi senza sovrascrivere. Cambiare branch non ripristina i file ignorati.
