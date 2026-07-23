# Ethical-Christian Guidelines – Preceptly

## Principles

Preceptly is guided by ethical-Christian values that are reflected in development, code, and handling of user data.

### Core Principles

1. **Honesty and Transparency**
   - No hidden functions
   - Clear communication about functionalities
   - Transparent data usage

2. **Order and Clarity**
   - Structured, comprehensible code
   - Clear documentation
   - Clear user interface

3. **Service to the User**
   - The tool should help the user work more structured and responsibly
   - No manipulative logic
   - Respectful handling of user data

4. **No Data Misuse**
   - Minimal data collection (only what is necessary)
   - No sharing of data with third parties without consent
   - Secure storage and processing

5. **Respectful Treatment**
   - Respectful language in code and user interface
   - No discriminatory or offensive content

## Biblical Reference

The style of the software should be characterized by order and reliability. No theological statements are forced in the code, but values such as faithfulness, clarity, and responsibility should be reflected in the product.

## Privacy

### Data Minimization
- Only data necessary for functionality is collected
- No unnecessary storage of personal information

### Transparency
- Users are informed about data usage
- Clear privacy policy
- **Transparency in time information and logs**: All timestamps and dates in the application use the timezone Europe/Berlin. This is clearly communicated in the documentation, and all log entries, timestamps, and dates are consistent in this timezone. Users are informed about the timezone used to avoid confusion.

### Security
- Secure storage of data
- Encryption of sensitive information
- **Security & Data Protection**:
  - Sensitive data (real student data, actual contracts) must **never** be committed to public repositories
  - Demo data is fictional and used only for demonstration purposes
  - Security vulnerabilities should be reported responsibly (see [SECURITY.md](../../SECURITY.md) for reporting guidelines)
  - All security-related findings are handled confidentially and addressed promptly
- Regular security checks

### Demo Data and Privacy
- **No real data in repository**: The repository contains no real student or customer data
- **Demo data is fictional**: All demo data (e.g., via `seed_demo_data` command) is completely fictional and serves only for demonstration purposes
- **Responsible handling**: Users are encouraged to handle personal data responsibly and comply with privacy regulations

## AI Usage (Premium Feature)

### Responsible AI Usage
- AI is only used for supporting functions (lesson plan generation)
- **Human-in-the-Loop**: AI-generated lesson plans are only suggestions and must be reviewed, adjusted, and verified by the tutor
- Users retain full control over generated content
- Clear labeling of AI-generated content (model name is stored)
- No manipulation or deception through AI

### Transparency
- Users are informed when AI is used
- Generated content can be reviewed and adjusted by the user
- The LLM model used is documented

### Privacy in AI Usage
- **Minimal data collection**: Only the most necessary information is sent to the LLM API:
  - Student name (first name, last name)
  - Grade level
  - Subject
  - Lesson duration
  - Lesson notes (if available)
- **No sensitive data**: The following data is NOT sent to the API:
  - Full addresses
  - Phone numbers or email addresses
  - Personal notes that are not relevant for lesson planning
- **Local storage**: Generated plans are stored locally in the database, not with the LLM API
- **API Keys**: API keys are configured via environment variables, not stored in code

## Hackathon Compliance

### Copyright
- No copying of complete projects or larger code blocks from other repositories
- Open-source libraries are used but must be mentioned in the README

### Fairness
- AI tools (Cursor, ChatGPT, etc.) are allowed, but there is meaningful human involvement
- No violation of copyright or intellectual property
- No prohibited or inappropriate content

## Implementation in Code

These principles should be reflected in the code:

- Clear, understandable code structure
- Good documentation
- Error handling without hiding problems
- Validation of all inputs
- Logging for traceability (without excess)

## Continuous Review

These guidelines are regularly reviewed and adjusted as needed to ensure that Preceptly meets ethical standards.
