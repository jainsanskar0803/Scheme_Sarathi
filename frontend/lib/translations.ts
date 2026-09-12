export type Lang = 'en' | 'hi'

export type Translations = {
  langEn: string; langHi: string
  backHome: string; backCitizens: string; profileComplete: string
  turnOffVoice: string; turnOnVoice: string; stillNeeded: string
  recording: string; stop: string; transcribing: string
  inputPlaceholder: string; voiceHint: string; voiceOn: string
  turnOffVoiceBtn: string; interviewDone: string
  profileReady: (pct: number) => string
  findBenefits: string; evaluatingSchemesBtn: string
  startingSession: string; loadingInterview: string
  interviewDoneMsg: string; interviewDoneMsgHi: string
  loadingResults: string; yourResults: string; refineProfile: string
  evaluatedSchemes: (total: number, worth: number) => string
  tabEligible: string; tabNearMiss: string; tabNeedInfo: string; notEligible: string
  searchPlaceholder: string; allCategories: string
  sortBestMatch: string; sortAlpha: string; sortBySource: string
  showingOf: (shown: number, total: number) => string
  matching: string; inCategory: string
  loadMore: (n: number) => string
  showingCount: (shown: number, total: number) => string
  benefit: string; whyQualify: string; documentsNeeded: string
  conditionsNotChecked: (n: number) => string
  fullDetails: string; eligibleBadge: string; nearMissBadge: string; needInfoBadge: string
  whatsHoldingBack: string; yourValue: string; requirementIs: string; gap: string
  conditionsYouMeet: string; viewFullDetails: string; viewDetails: string
  completeProfile: string; tellUsToCheck: string; alreadyConfirmed: string; yourProfile: string
  noEligibleTitle: string; noEligibleBody: string
  noNearMissTitle: string; noNearMissBody: string
  noNeedInfoTitle: string; noNeedInfoBody: string
  noFilterMatch: string; clearFilters: string
  refineMyProfile: string; newSession: string; completeProfileBtn: string
  evaluatingSchemes: string; justAMoment: string
  somethingWrong: string; startOver: string
  loadingCategories: string[]
  disabled: string; bpl: string; yrs: string; perYr: string
  showLess: string; moreConditions: (n: number) => string
  backToSchemeDetails: string; documentVerification: string; docVerifySubtitle: string
  verifiedCount: (confirmed: number, total: number) => string
  allVerified: string; noticeLabel: string; noticeText: string
  statusMissing: string; statusVerifying: string; statusRejected: string
  statusMismatch: string; statusNeedsConfirm: string; statusVerified: string
  tapOrDrag: string; photoOrPdf: string; verifyingDoc: string
  notValidDoc: string; wrongDocType: string; uploadCorrect: string
  detailsMismatch: string; confirmAnyway: string; replace: string
  confirmDoc: string; removeReupload: string; identifiedAs: string
  highConfidence: string; medConfidence: string; lowConfidence: string
  fieldCol: string; profileCol: string; docCol: string; matchCol: string
  notVisible: string; backToSchemeDetailsBtn: string
  noDocListTitle: string; noDocListBody: string; backToResults: string
  typeMatchNote: string; detected: string; verified: string; matched: string
}

const en: Translations = {
  // ── Language toggle ──────────────────────────────────────────────────────
  langEn: 'EN',
  langHi: 'हिं',

  // ── Interview page ───────────────────────────────────────────────────────
  backHome: '← Home',
  backCitizens: '← Citizens',
  profileComplete: 'Profile Complete',
  turnOffVoice: 'Turn off voice responses',
  turnOnVoice: 'Turn on voice responses',
  stillNeeded: 'Still needed:',
  recording: 'Recording… speak now',
  stop: 'Stop',
  transcribing: 'Transcribing…',
  inputPlaceholder: 'Type your message… (Enter to send, Shift+Enter for new line)',
  voiceHint: 'Tap 🎤 to speak in Hindi, English, or Hinglish',
  voiceOn: '🔊 Voice responses on',
  turnOffVoiceBtn: 'Turn off voice',
  interviewDone: 'Interview complete!',
  profileReady: (pct: number) => `Profile ${pct}% complete — ready to find schemes!`,
  findBenefits: 'Find My Benefits',
  evaluatingSchemesBtn: 'Evaluating schemes...',
  startingSession: 'Starting your session...',
  loadingInterview: 'Loading interview...',
  interviewDoneMsg: "Great! I have enough information to find relevant schemes for you. Click the button below to see your results.",
  interviewDoneMsgHi: 'बढ़िया! आपकी सभी जानकारी मिल गई। अपनी योजनाएं देखने के लिए नीचे का बटन दबाएं।',

  // ── Results page ─────────────────────────────────────────────────────────
  loadingResults: 'Loading results…',
  yourResults: 'Your Results',
  refineProfile: 'Refine Profile',
  evaluatedSchemes: (total: number, worth: number) =>
    `Evaluated ${total.toLocaleString()} schemes · ${worth} worth reviewing`,
  tabEligible: 'Eligible',
  tabNearMiss: 'Near Miss',
  tabNeedInfo: 'Need Info',
  notEligible: 'Not Eligible',
  searchPlaceholder: 'Search schemes…',
  allCategories: 'All Categories',
  sortBestMatch: 'Best Match First',
  sortAlpha: 'A → Z',
  sortBySource: 'By Source',
  showingOf: (shown: number, total: number) => `Showing ${shown} of ${total} schemes`,
  matching: 'matching',
  inCategory: 'in',
  loadMore: (n: number) => `Load ${n} more`,
  showingCount: (shown: number, total: number) => `Showing ${shown} of ${total}`,
  benefit: 'Benefit',
  whyQualify: 'Why you qualify',
  documentsNeeded: 'Documents needed',
  conditionsNotChecked: (n: number) => `${n} condition${n > 1 ? 's' : ''} not checked`,
  fullDetails: 'Full Details →',
  eligibleBadge: '✓ Eligible',
  nearMissBadge: '~ Almost Eligible',
  needInfoBadge: '? Need More Info',
  whatsHoldingBack: "What's holding you back",
  yourValue: 'Your value is',
  requirementIs: 'but requirement is',
  gap: 'Gap:',
  conditionsYouMeet: 'Conditions you meet',
  viewFullDetails: 'View Full Details →',
  viewDetails: 'View Details',
  completeProfile: 'Complete Profile →',
  tellUsToCheck: 'Tell us to check eligibility',
  alreadyConfirmed: 'Already confirmed',
  yourProfile: 'Your profile:',
  noEligibleTitle: 'No eligible schemes found',
  noEligibleBody: 'Try completing more of your profile to unlock matches.',
  noNearMissTitle: 'No near-miss schemes',
  noNearMissBody: 'Either you fully qualify or are too far from eligibility for these schemes.',
  noNeedInfoTitle: 'No missing information',
  noNeedInfoBody: 'Great — your profile is complete enough to check all schemes.',
  noFilterMatch: 'No schemes match your current filters.',
  clearFilters: 'Clear filters',
  refineMyProfile: 'Refine My Profile',
  newSession: 'New Session',
  completeProfileBtn: 'Complete Profile',
  evaluatingSchemes: 'Evaluating 3,397 schemes…',
  justAMoment: 'This takes just a moment',
  somethingWrong: 'Something went wrong',
  startOver: 'Start Over',
  loadingCategories: ['Education', 'Agriculture', 'Health', 'Housing', 'Skills'],
  disabled: 'Disabled',
  bpl: 'BPL',
  yrs: 'yrs',
  perYr: '/yr',
  showLess: 'Show less',
  moreConditions: (n: number) => `+${n} more conditions`,

  // ── Documents page ───────────────────────────────────────────────────────
  backToSchemeDetails: '← Scheme Details',
  documentVerification: 'Document Verification',
  docVerifySubtitle: 'Upload each document. We verify the type and check that the details match your profile.',
  verifiedCount: (confirmed: number, total: number) => `${confirmed} of ${total} verified`,
  allVerified: 'All documents verified!',
  noticeLabel: 'Notice:',
  noticeText: 'Verification is based on visual features only. Scheme Sarathi does not connect to any government database and cannot confirm document authenticity. Always verify with the scheme authority.',
  statusMissing: 'Missing',
  statusVerifying: 'Verifying…',
  statusRejected: 'Rejected',
  statusMismatch: 'Details Mismatch',
  statusNeedsConfirm: 'Needs Confirmation',
  statusVerified: 'Verified',
  tapOrDrag: 'Tap or drag to upload',
  photoOrPdf: 'Photo (JPG / PNG / WEBP) or PDF scan',
  verifyingDoc: 'Verifying document…',
  notValidDoc: 'Not a Valid Document',
  wrongDocType: 'Wrong Document Type',
  uploadCorrect: 'Upload Correct Document',
  detailsMismatch: "Details don't fully match your profile",
  confirmAnyway: 'Confirm Anyway',
  replace: 'Replace',
  confirmDoc: '✓ Confirm Document',
  removeReupload: 'Remove and re-upload',
  identifiedAs: 'Identified as:',
  highConfidence: 'High confidence',
  medConfidence: 'Medium confidence',
  lowConfidence: 'Low confidence',
  fieldCol: 'Field',
  profileCol: 'Your Profile',
  docCol: 'On Document',
  matchCol: 'Match',
  notVisible: 'not visible',
  backToSchemeDetailsBtn: '← Back to Scheme Details',
  noDocListTitle: 'No document list found',
  noDocListBody: 'This scheme may not have a required documents list, or your session has expired.',
  backToResults: '← Back to Results',
  typeMatchNote: "Document type matches. Some fields couldn't be verified — confirm if this is the correct document.",
  detected: 'Detected:',
  verified: 'verified',
  matched: 'matched',
}

const hi: Translations = {
  // ── Language toggle ──────────────────────────────────────────────────────
  langEn: 'EN',
  langHi: 'हिं',

  // ── Interview page ───────────────────────────────────────────────────────
  backHome: '← होम',
  backCitizens: '← नागरिक',
  profileComplete: 'प्रोफ़ाइल पूर्णता',
  turnOffVoice: 'आवाज़ बंद करें',
  turnOnVoice: 'आवाज़ चालू करें',
  stillNeeded: 'अभी चाहिए:',
  recording: 'रिकॉर्डिंग… अभी बोलें',
  stop: 'रोकें',
  transcribing: 'लिखा जा रहा है…',
  inputPlaceholder: 'संदेश लिखें… (Enter भेजें, Shift+Enter नई लाइन)',
  voiceHint: '🎤 दबाएं — हिंदी, अंग्रेज़ी या Hinglish में बोलें',
  voiceOn: '🔊 आवाज़ उत्तर चालू',
  turnOffVoiceBtn: 'आवाज़ बंद करें',
  interviewDone: 'साक्षात्कार पूर्ण!',
  profileReady: (pct: number) => `प्रोफ़ाइल ${pct}% पूर्ण — योजनाएं खोजने के लिए तैयार!`,
  findBenefits: 'मेरे लाभ खोजें',
  evaluatingSchemesBtn: 'योजनाएं जांची जा रही हैं...',
  startingSession: 'सत्र शुरू हो रहा है...',
  loadingInterview: 'साक्षात्कार लोड हो रहा है...',
  interviewDoneMsg: 'बढ़िया! आपकी सभी जानकारी मिल गई। अपनी योजनाएं देखने के लिए नीचे का बटन दबाएं।',
  interviewDoneMsgHi: 'बढ़िया! आपकी सभी जानकारी मिल गई। अपनी योजनाएं देखने के लिए नीचे का बटन दबाएं।',

  // ── Results page ─────────────────────────────────────────────────────────
  loadingResults: 'परिणाम लोड हो रहे हैं…',
  yourResults: 'आपके परिणाम',
  refineProfile: 'प्रोफ़ाइल सुधारें',
  evaluatedSchemes: (total: number, worth: number) =>
    `${total.toLocaleString('hi-IN')} योजनाओं का मूल्यांकन · ${worth} देखने योग्य`,
  tabEligible: 'पात्र',
  tabNearMiss: 'लगभग पात्र',
  tabNeedInfo: 'जानकारी चाहिए',
  notEligible: 'अपात्र',
  searchPlaceholder: 'योजनाएं खोजें…',
  allCategories: 'सभी श्रेणियां',
  sortBestMatch: 'सर्वश्रेष्ठ मिलान पहले',
  sortAlpha: 'A → Z',
  sortBySource: 'स्रोत के अनुसार',
  showingOf: (shown: number, total: number) => `${total} में से ${shown} योजनाएं`,
  matching: 'खोज',
  inCategory: 'श्रेणी में',
  loadMore: (n: number) => `${n} और लोड करें`,
  showingCount: (shown: number, total: number) => `${shown} में से ${total} दिखाई जा रही हैं`,
  benefit: 'लाभ',
  whyQualify: 'आप क्यों योग्य हैं',
  documentsNeeded: 'आवश्यक दस्तावेज़',
  conditionsNotChecked: (n: number) => `${n} शर्त${n > 1 ? 'ें' : ''} जांची नहीं गई`,
  fullDetails: 'पूरी जानकारी →',
  eligibleBadge: '✓ पात्र',
  nearMissBadge: '~ लगभग पात्र',
  needInfoBadge: '? अधिक जानकारी चाहिए',
  whatsHoldingBack: 'आपको क्या रोक रहा है',
  yourValue: 'आपका मान है',
  requirementIs: 'लेकिन आवश्यकता है',
  gap: 'अंतर:',
  conditionsYouMeet: 'आप जो शर्तें पूरी करते हैं',
  viewFullDetails: 'पूरी जानकारी देखें →',
  viewDetails: 'जानकारी देखें',
  completeProfile: 'प्रोफ़ाइल पूरी करें →',
  tellUsToCheck: 'पात्रता जांचने के लिए बताएं',
  alreadyConfirmed: 'पहले से पुष्टि',
  yourProfile: 'आपकी प्रोफ़ाइल:',
  noEligibleTitle: 'कोई पात्र योजना नहीं मिली',
  noEligibleBody: 'अधिक मिलान पाने के लिए अपनी प्रोफ़ाइल पूरी करें।',
  noNearMissTitle: 'कोई लगभग-पात्र योजना नहीं',
  noNearMissBody: 'आप या तो पूरी तरह योग्य हैं या इन योजनाओं के लिए बहुत दूर हैं।',
  noNeedInfoTitle: 'कोई जानकारी नहीं छूटी',
  noNeedInfoBody: 'बढ़िया — आपकी प्रोफ़ाइल सभी योजनाओं की जांच के लिए पर्याप्त है।',
  noFilterMatch: 'आपके फ़िल्टर से कोई योजना नहीं मिली।',
  clearFilters: 'फ़िल्टर साफ़ करें',
  refineMyProfile: 'मेरी प्रोफ़ाइल सुधारें',
  newSession: 'नया सत्र',
  completeProfileBtn: 'प्रोफ़ाइल पूरी करें',
  evaluatingSchemes: '3,397 योजनाओं का मूल्यांकन हो रहा है…',
  justAMoment: 'इसमें बस एक पल लगेगा',
  somethingWrong: 'कुछ गलत हुआ',
  startOver: 'फिर से शुरू करें',
  loadingCategories: ['शिक्षा', 'कृषि', 'स्वास्थ्य', 'आवास', 'कौशल'],
  disabled: 'विकलांग',
  bpl: 'बीपीएल',
  yrs: 'वर्ष',
  perYr: '/वर्ष',
  showLess: 'कम दिखाएं',
  moreConditions: (n: number) => `+${n} और शर्तें`,

  // ── Documents page ───────────────────────────────────────────────────────
  backToSchemeDetails: '← योजना विवरण',
  documentVerification: 'दस्तावेज़ सत्यापन',
  docVerifySubtitle: 'प्रत्येक दस्तावेज़ अपलोड करें। हम प्रकार सत्यापित करते हैं और जांचते हैं कि विवरण आपकी प्रोफ़ाइल से मेल खाते हैं।',
  verifiedCount: (confirmed: number, total: number) => `${total} में से ${confirmed} सत्यापित`,
  allVerified: 'सभी दस्तावेज़ सत्यापित!',
  noticeLabel: 'सूचना:',
  noticeText: 'सत्यापन केवल दृश्य विशेषताओं पर आधारित है। Scheme Sarathi किसी भी सरकारी डेटाबेस से नहीं जुड़ता और दस्तावेज़ की प्रामाणिकता की पुष्टि नहीं कर सकता। हमेशा योजना प्राधिकरण से सत्यापित करें।',
  statusMissing: 'गायब',
  statusVerifying: 'सत्यापित हो रहा है…',
  statusRejected: 'अस्वीकृत',
  statusMismatch: 'विवरण मेल नहीं खाते',
  statusNeedsConfirm: 'पुष्टि चाहिए',
  statusVerified: 'सत्यापित',
  tapOrDrag: 'अपलोड करने के लिए टैप या खींचें',
  photoOrPdf: 'फोटो (JPG / PNG / WEBP) या PDF स्कैन',
  verifyingDoc: 'दस्तावेज़ सत्यापित हो रहा है…',
  notValidDoc: 'वैध दस्तावेज़ नहीं',
  wrongDocType: 'गलत दस्तावेज़ प्रकार',
  uploadCorrect: 'सही दस्तावेज़ अपलोड करें',
  detailsMismatch: 'विवरण आपकी प्रोफ़ाइल से पूरी तरह मेल नहीं खाते',
  confirmAnyway: 'फिर भी पुष्टि करें',
  replace: 'बदलें',
  confirmDoc: '✓ दस्तावेज़ पुष्टि करें',
  removeReupload: 'हटाएं और फिर अपलोड करें',
  identifiedAs: 'पहचाना गया:',
  highConfidence: 'उच्च विश्वास',
  medConfidence: 'मध्यम विश्वास',
  lowConfidence: 'कम विश्वास',
  fieldCol: 'क्षेत्र',
  profileCol: 'आपकी प्रोफ़ाइल',
  docCol: 'दस्तावेज़ पर',
  matchCol: 'मिलान',
  notVisible: 'दिखाई नहीं देता',
  backToSchemeDetailsBtn: '← योजना विवरण पर वापस',
  noDocListTitle: 'दस्तावेज़ सूची नहीं मिली',
  noDocListBody: 'इस योजना में आवश्यक दस्तावेज़ों की सूची नहीं हो सकती, या आपका सत्र समाप्त हो गया है।',
  backToResults: '← परिणामों पर वापस',
  typeMatchNote: 'दस्तावेज़ प्रकार मेल खाता है। कुछ क्षेत्र सत्यापित नहीं हो सके — यदि यह सही दस्तावेज़ है तो पुष्टि करें।',
  detected: 'पहचाना:',
  verified: 'सत्यापित',
  matched: 'मिलान',
}

export const translations: Record<Lang, Translations> = { en, hi }

export function t(lang: Lang): Translations {
  return translations[lang]
}
