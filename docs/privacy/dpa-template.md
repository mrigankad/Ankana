# Data Processing Agreement (template)

> **DRAFT, NEEDS LAWYER REVIEW.** This is an engineering-authored starting point, not legal advice. Do not
> send it to a practice until counsel has reviewed it against the DPDP Act 2023, the DPDP Rules 2025 and the
> commercial terms. Square-bracketed items are placeholders.

Between **[Practice legal name]**, [address] ("**Fiduciary**") and **[Ankana operating entity]**, [address]
("**Processor**"). Effective date: [date]. Governed by the Ankana subscription terms ("**Main Agreement**").

## 1. Roles and scope

1.1 For personal data of the Fiduciary's clients ("**Client Data**") that the Processor processes through the
Ankana service, the Fiduciary determines the purposes and means and is the data fiduciary under the Digital
Personal Data Protection Act, 2023 ("**DPDP Act**"). The Processor acts only on the Fiduciary's documented
instructions, which are this Agreement, the Main Agreement and the Fiduciary's use of the service.

1.2 Subject matter, nature and purpose: hosting, storing and computing astrological charts, reports,
consultation notes, remedy plans and related records for the Fiduciary's practice. Categories of data
principals: the Fiduciary's clients and prospective clients. Categories of data: name, email, phone, date, time
and place of birth, consultation notes, remedy records, consent records. See the data map in `docs/privacy.md`.

1.3 The Processor will not use Client Data to train models, for advertising, or for any purpose of its own.

## 2. Fiduciary obligations

The Fiduciary is responsible for: giving each client a notice that meets the DPDP Act (template provided),
obtaining and recording consent per purpose, the accuracy of data it enters, and responding to data
principals. The Fiduciary will not instruct the Processor to act in breach of law.

## 3. Processor obligations

3.1 **Security.** Reasonable security safeguards, including: per-practice field-level encryption (AES-256-GCM)
of contact details, birth place and notes with keys held outside the database; tenant isolation by row-level
security; encryption in transit; access logging; least-privilege access for staff. Measures are described in
`docs/privacy.md` and may be improved but not materially weakened.

3.2 **Confidentiality.** Personnel with access are bound by confidentiality.

3.3 **Sub-processors.** The Fiduciary gives general authorisation for the sub-processors listed in Annex 2.
The Processor will flow down equivalent obligations and give [30] days' notice of changes; the Fiduciary may
object on reasonable grounds.

3.4 **Assistance with data principal rights.** The service provides export (access and portability), correction
with a change log, erasure with legal-hold support, retention controls and consent receipts. The Processor
will forward any request it receives directly to the Fiduciary within [5] business days.

3.5 **Breach.** The Processor will notify the Fiduciary without undue delay and within [48] hours of becoming
aware of a personal data breach affecting Client Data, with the information reasonably available (nature,
categories, approximate scale, likely consequences, measures taken), so the Fiduciary can meet its duty to
notify the Data Protection Board and affected data principals.

3.6 **Audit.** On [30] days' notice and no more than once a year, the Processor will provide information
reasonably needed to show compliance, and allow an audit by the Fiduciary or its auditor under confidentiality.

## 4. Location and transfers

Client Data is hosted in [India region]. The Processor will not transfer Client Data outside India except to
the Annex 2 sub-processors identified as doing so, and only to the extent permitted by the DPDP Act and any
restriction notified by the Central Government. [Counsel: confirm.]

## 5. Retention, return and deletion

5.1 Retention follows the Fiduciary's configured settings. On a data principal's erasure request executed by
the Fiduciary, the Processor's tooling erases the client's records and stored files and keeps a minimal
tombstone and audit entry (see `docs/privacy.md`).

5.2 On termination the Fiduciary may export all data for [30] days; afterwards the Processor deletes Client
Data and destroys the encryption keys, except what law requires to be retained (for example billing records).
Backups expire within [35] days of deletion.

## 6. Liability and term

[Counsel to complete: liability allocation, indemnities, term and termination, order of precedence versus the
Main Agreement, governing law and forum.]

## Annex 1: Technical and organisational measures
[Summarise `docs/privacy.md` sections 1 to 4; infrastructure controls from the deployment documentation.]

## Annex 2: Sub-processors
| Name | Purpose | Location |
|---|---|---|
| [Cloud provider, e.g. Microsoft Azure] | hosting, storage, key vault | [India] |
| [LLM provider, e.g. Anthropic] | AI assistant (charts only, no names or contact details) | [location] |
| [Email provider, e.g. Azure Communication Services] | transactional email and OTP | [location] |
| [Payments, Razorpay] | subscription billing (practice data only) | India |

Signed: ____________________ (Fiduciary)    ____________________ (Processor)
