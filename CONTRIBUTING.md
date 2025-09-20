# Contributing to Genesis Trading Bot

Tack för ditt intresse att bidra till Genesis Trading Bot! Detta dokument beskriver hur du kan bidra till projektet.

## 🚀 Snabbstart för bidragsgivare

1. **Forka** repositoryt
2. **Skapa** en feature branch (`git checkout -b feature/amazing-feature`)
3. **Commita** dina ändringar (`git commit -m 'Add some amazing feature'`)
4. **Pusha** till branchen (`git push origin feature/amazing-feature`)
5. **Öppna** en Pull Request

## 📋 Utvecklingsstandarder

### Kodkvalitet

- **Formatering:** Använd Black för Python-kod
- **Linting:** Använd Ruff för Python-linting
- **Säkerhet:** Kör Bandit för säkerhetsanalys
- **Tester:** Skriv tester för nya funktioner
- **Typing:** Använd type hints där möjligt

### Commits

- Använd tydliga och beskrivande commit-meddelanden
- Följ [Conventional Commits](https://www.conventionalcommits.org/) format
- Exempel: `feat: add new trading strategy`, `fix: resolve WebSocket connection issue`

### Pull Requests

- Skapa tydlig PR-beskrivning med motivation och teststeg
- Inkludera relevanta testresultat
- Uppdatera dokumentation vid behov
- Kör alla tester innan PR

## 🧪 Testning

### Backend

```powershell
# Kör alla tester
python -m pytest tests/ -v

# Med coverage
python -m pytest tests/ --cov=services --cov-report=html

# Specifika tester
python -m pytest tests/test_unified_config_system.py -v
```

### Frontend

```bash
# Kör tester
npm test

# Linting
npm run lint
```

## 🛠️ Utvecklingsmiljö

### Backend Setup

```powershell
# Skapa virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Installera dependencies
pip install -r requirements.txt

# Starta utvecklingsserver
python -m uvicorn main:app --reload
```

### Frontend Setup

```bash
# Installera dependencies
npm install

# Starta utvecklingsserver
npm run dev
```

## 📝 Dokumentation

- Uppdatera README-filer vid behov
- Lägg till docstrings för nya funktioner
- Dokumentera API-ändringar
- Uppdatera TODO-listor

## 🐛 Bug Reports

När du rapporterar buggar, inkludera:

- **Beskrivning** av problemet
- **Steg för att reproducera**
- **Förväntat beteende**
- **Faktiskt beteende**
- **Miljöinformation** (OS, Python-version, etc.)
- **Loggar** om tillgängliga

## 💡 Feature Requests

För nya funktioner:

- Beskriv funktionen och dess användningsfall
- Förklara varför den skulle vara användbar
- Inkludera eventuella mockups eller exempel
- Överväg implementation-komplexitet

## 🔒 Säkerhet

- Rapportera säkerhetsbrister privat via e-post
- Inkludera detaljerad beskrivning
- Vi svarar inom 48 timmar
- **INTE** skapa public issues för säkerhetsproblem

## 📞 Kontakt

- **Issues:** Använd GitHub Issues för buggar och feature requests
- **Discussions:** Använd GitHub Discussions för frågor
- **Security:** E-post för säkerhetsproblem

## 📄 License

Genom att bidra till detta projekt godkänner du att dina bidrag licensieras under MIT License.

---

Tack för ditt bidrag! 🎉
