import { CaretRightIcon } from '@phosphor-icons/react/dist/ssr';
import type { Metadata } from 'next';
import { DpaRequestForm } from './dpa-form';
import { OpenOnHash } from './open-on-hash';
import { Eyebrow } from '@/components/ui/panel';

export const metadata: Metadata = {
  title: 'Trust',
  description:
    'How CallFlow places calls, what is disclosed to the person answering, how consent and opt-outs are handled, and how call data is retained and deleted.',
};

/**
 * Trust.
 *
 * Set as a single narrow column of ruled prose, with no cards and no illustration.
 * This page should read like a document, because that is what earns trust - a
 * compliance reviewer skimming for retention windows and sub-processors is looking
 * for a document, and dressing it up as marketing makes them trust it less.
 *
 * **Every section leads with its answer, and the detail folds away.** The page
 * had a real problem under the document framing: 1,100 words across 43
 * paragraphs, seventeen of them over thirty words, and nothing on screen a
 * reader could take at a glance. But the two audiences here want opposite
 * things - a buyer wants to know in five seconds whether opt-outs are
 * permanent; a data-protection reviewer wants the paragraph saying exactly how.
 * Serving one by deleting the other's material would be the wrong trade on the
 * one page where being complete *is* the claim.
 *
 * So `answer` is the section, and the paragraphs are its evidence. Nothing was
 * removed except two sentences that appeared twice. Collapsed, the page is eight
 * headings and eight one-line answers; expanded, it is the document it was.
 *
 * Sub-processors are listed by category and function. Naming vendors here would
 * put third-party branding into the product's most scrutinised page and would need
 * re-approving every time a supplier changed.
 */

const SECTIONS = [
  {
    id: 'how-calls-are-placed',
    heading: 'How calls are placed, and what the person answering is told',
    answer:
      'The agent says it is an automated assistant in the opening seconds, and never claims to be a person. Recording is off unless you turn it on.',
    paragraphs: [
      'Every call is placed to a single number, from a caller ID you have verified as yours. Calls originate from our infrastructure; there is no dialler running on your machines and no telephony stack for you to maintain.',
      'The agent identifies itself in the opening seconds. It says which organisation it is calling on behalf of and states that it is an automated assistant. That disclosure line is on by default, it is editable so it can match your own wording and language, and it cannot be removed entirely.',
      'The agent will not claim to be a human being. If someone asks directly whether they are speaking to a person, it answers honestly and offers to hand over.',
      'Recording is off unless you turn it on. Where you do enable it, the disclosure line is extended to say so before the conversation begins.',
    ],
  },
  {
    id: 'consent',
    heading: 'Consent, and how it lands as a typed field',
    answer:
      'You bring the lawful basis to call. Where a campaign needs consent on the call itself, it comes back as a typed boolean, not a guess from prose.',
    paragraphs: [
      'You are responsible for having a lawful basis to call the people on your list - usually because they enquired, are an existing customer, or gave consent. CallFlow does not source phone numbers and never supplies contacts.',
      'Where a campaign needs consent captured on the call itself, turn on the consent requirement in Settings → Compliance. The agent then asks for it explicitly and the answer comes back as a typed boolean alongside the words used, so it is auditable rather than inferred from prose.',
      'A campaign with the consent requirement on will not record a result as complete if consent was refused. The call ends politely and the contact is suppressed.',
    ],
  },
  {
    id: 'opt-outs',
    heading: 'Opt-outs and the suppression list',
    answer:
      'An opt-out ends the call and suppresses the number permanently, across every campaign, checked before every dial.',
    paragraphs: [
      'If someone asks not to be called again - in any phrasing the agent recognises as an opt-out - the call ends and the number is added to your suppression list immediately.',
      'The suppression list is global and permanent. It applies across every campaign in your organisation, forever, and it cannot be overridden from a run. A suppressed number is skipped before a call is placed, and the row says why.',
      'You can also add numbers manually or import a do-not-call list in bulk. Suppression survives contact re-imports: re-uploading a CSV that contains a suppressed number does not resurrect it.',
    ],
  },
  {
    id: 'number-masking',
    heading: 'Phone number masking',
    answer:
      'Numbers are masked everywhere by default - country prefix and the last three digits. Revealing one is a separate, permissioned action.',
    paragraphs: [
      'Phone numbers are masked everywhere in the interface by default - in tables, run views, transcripts, exports shown on screen, and error messages. What you see is the country prefix and the last three digits.',
      'Revealing a full number is a separate action, available only to roles you have granted it to. Masking is implemented in exactly one place in the codebase, so a new screen cannot accidentally ship without it.',
      'Logs written by the service mask numbers the same way. A full number is not written to an application log.',
    ],
  },
  {
    id: 'retention',
    heading: 'Data retention and deletion',
    answer:
      'Transcripts and recordings expire on your window and are deleted, not archived. Typed results stay, so reporting survives them.',
    paragraphs: [
      'Transcripts and recordings are kept for the window on your plan, and you can shorten that window on any plan, including Free. When the window passes they are deleted, not archived.',
      'Typed results - outcome, sentiment, and your own fields - are kept for the life of the account so your reporting stays intact after transcripts expire. They contain no audio and no full phone numbers.',
      'You can export everything as CSV or JSON at any time, and you can request deletion of an individual contact or of the whole organisation from Settings → Compliance. Deletion requests are honoured within 30 days and cover backups.',
    ],
  },
  {
    id: 'sub-processors',
    heading: 'Sub-processors',
    answer:
      'Six categories of infrastructure provider. The current named list, with jurisdictions, ships with the DPA.',
    paragraphs: [
      'CallFlow relies on a small number of infrastructure providers, listed by category and function - the level of detail a data-protection assessment needs.',
    ],
    list: [
      'Voice and telephony - places the call, handles speech and turn-taking. Receives the phone number, the campaign goal, and the result schema.',
      'Cloud hosting and compute - runs the service. Receives all data processed by the platform.',
      'Managed database and object storage - stores campaigns, results, transcripts, and recordings at rest.',
      "Transactional email - sends account, verification, and notification email. Receives your users' email addresses, never contact data.",
      'Payment processing - handles card details and invoicing. Card numbers never reach our systems.',
      'Error monitoring and logging - receives operational telemetry with phone numbers masked.',
    ],
  },
  {
    id: 'regional',
    heading: 'Regional compliance notes',
    answer:
      'India, the EU and UK, and the US each need something different from you. Calling-hour restrictions are not enforced by the product - that is yours until they are.',
    paragraphs: [
      'India - where a campaign targets numbers registered on a national do-not-call preference list, you are responsible for scrubbing against it; import the list into your suppression list and it will be enforced on every run, checked before every dial, permanently.',
      'European Union and United Kingdom - a DPA including the standard contractual clauses is available. Data residency in the EU can be arranged on Enterprise. Automated calling to individuals generally requires prior consent, and the consent-capture setting exists for exactly that.',
      'United States - consent requirements for automated calls vary by state and are stricter than for manual dialling; take your own advice before running a live campaign.',
      'None of the above is legal advice. The guards exist so that your policy can be enforced by the product rather than remembered by a person.',
    ],
  },
  {
    id: 'security',
    heading: 'Security and reporting a problem',
    answer:
      'Encrypted in transit and at rest, production access logged and behind MFA. Vulnerabilities to security@callflow.ai, acknowledged in two business days.',
    paragraphs: [
      'Data is encrypted in transit and at rest. Access to production is limited, logged, and requires multi-factor authentication. API keys are shown once at creation, stored hashed, and can be revoked immediately.',
      'If you believe you have found a vulnerability, email security@callflow.ai. We will acknowledge within two business days. Please do not run automated scanning against live calling endpoints - a test that places real calls reaches real people.',
    ],
  },
];

export default function TrustPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 pt-12 sm:px-6">
      <OpenOnHash />
      <header className="flex flex-col gap-4">
        <Eyebrow>Trust</Eyebrow>
        <h1 className="font-display text-display-l text-text">
          How this works, and what we do with the data.
        </h1>
        <p className="text-body-l text-text-dim">
          CallFlow places real phone calls to real people. This page describes
          exactly what happens on those calls, what the person answering is
          told, and what becomes of the recording afterwards.
        </p>
      </header>

      {/* A table of contents, because this page is read by someone looking for one
          specific answer far more often than it is read top to bottom. */}
      <nav
        aria-label="On this page"
        className="mt-10 border-y border-rule py-5"
      >
        <Eyebrow>On this page</Eyebrow>
        <ul className="mt-3 flex flex-col gap-1.5">
          {SECTIONS.map((section) => (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                className="text-small text-text-dim underline decoration-rule-strong underline-offset-4 transition-colors hover:text-text hover:decoration-current"
              >
                {section.heading}
              </a>
            </li>
          ))}
          <li>
            <a
              href="#dpa"
              className="text-small text-text-dim underline decoration-rule-strong underline-offset-4 transition-colors hover:text-text hover:decoration-current"
            >
              Request our DPA
            </a>
          </li>
        </ul>
      </nav>

      <div className="flex flex-col">
        {SECTIONS.map((section) => (
          <section
            key={section.id}
            id={section.id}
            className="border-b border-rule py-8 last:border-0"
          >
            <h2 className="font-display text-h3 text-text">
              {section.heading}
            </h2>
            {/* The answer is body-large at full text strength; the detail
                under it is neither. Same hierarchy the headings already use,
                one level down. */}
            <p className="mt-3 text-body-l text-text">{section.answer}</p>

            <details className="disclosure group mt-4">
              <summary className="text-small">
                <CaretRightIcon
                  aria-hidden
                  weight="bold"
                  className="disclosure-caret size-3.5"
                />
                <span className="underline decoration-rule-strong underline-offset-4 group-open:no-underline">
                  How it works in detail
                </span>
              </summary>

              <div className="flex flex-col gap-4 pt-4">
                {section.paragraphs.map((paragraph, i) => (
                  <p key={i} className="text-body text-text-dim">
                    {paragraph}
                  </p>
                ))}
                {section.list ? (
                  <ul className="flex flex-col gap-2.5 pt-1">
                    {section.list.map((item) => (
                      <li
                        key={item}
                        className="flex gap-3 text-body text-text-dim"
                      >
                        <span
                          aria-hidden
                          className="mt-[0.6em] size-1 shrink-0 rounded-full bg-rule-strong"
                        />
                        {item}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </details>
          </section>
        ))}
      </div>

      <section id="dpa" className="border-t border-rule py-8">
        <h2 className="font-display text-h3 text-text">Request our DPA</h2>
        <p className="mt-3 text-body text-text-dim">
          We will send the data processing agreement, the current named
          sub-processor list with jurisdictions, and our security overview.
        </p>
        <div className="mt-6">
          <DpaRequestForm />
        </div>
      </section>
    </div>
  );
}
