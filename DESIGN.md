q# TaskFlow desktop design

The user's reference is Notion: quiet neutral surfaces, compact task rows, subtle rules and minimal navigation. This is an operational desktop workspace for Windows and Linux.

## Layout

- Native resizable window: initial 1280 × 820, minimum 1040 × 600.
- Sidebar: 190; main horizontal inset: 24; main vertical inset: 30.
- Primary destinations: Công việc, Lịch làm việc, Chat AI, Báo cáo. Settings and account sit at the bottom.
- Projects are secondary links within tasks.
- Chat AI is a separate page; its reading/composer area is centered and bounded to 960 px. Keep conversation state across navigation.
- Editing uses a separate page and preserves model properties not exposed by the form.

## Tokens

Approved direction: subtle Vietnamese ink wash, with ivory paper rather than decorative scenery. Paper #F8F6F0, cards #FFFEFA, sidebar #F2F0E8, ink #1C1C19, muted #5E5D56, separators #DEDCD2. Provider logos keep their brand colors. The generated monochrome cat at assets/ink-cat.png is the assistant avatar; do not replace it with a generic chat symbol. This iteration implements the approved light palette; a matching dark theme remains separate work.

Page title: 28–30 / semibold; body: 17; navigation/buttons: 16; metadata: 14–16. Spacing: 6, 8, 12, 16, 20, 24, 32. Navigation corners: 5. Avoid decorative shadows, gradients, phone chrome and floating AI buttons in the desktop shell.

## Behavior

Tasks support search, active/today/all/completed filters, completion, editing and confirmed deletion. Reports use real task completion dates and due dates, with 1/7/30 day periods. The rate is explicitly the fraction of tasks due in the period whose status is completed. Daily bars use a shared scale within the selected period.

Health and behavioral intelligence remain in services; primary task, editor and report screens do not expose those measurements. System appearance changes must preserve unsaved text.

AI suggestions use real native checkboxes: empty initially, black fill and white tick when selected. Selection is independent for duplicate task titles. Saving selected suggestions binds to the account that owns the rendered plan, removes only successfully saved suggestions and leaves failures available for retry. Plans use a single readable column with numbered steps, rather than narrow nested cards.

The local demo uses a persistent “DEMO · Không thu tiền” notice and separate account/workspace databases. Google/Facebook buttons always initiate real OAuth; payment simulation exists only in the dedicated loopback demo service.

## Validation status

Native Linux screenshots reviewed at 1280 × 820 and 1040 × 600, including the actual Chat AI page with selected/unselected checkboxes, task list, login and registration. Windows visual verification remains outstanding. Automated coverage includes payment demo isolation, entitlement activation/idempotency, duplicate suggestions and retry after save failures.
