// Translation dictionary, context and hook (the provider component lives in ./i18n.tsx).
import { createContext, useContext } from "react";

export const dict = {
  en: {
    command: "Command Centre", map: "Risk Map", matrix: "Availability", expiry: "Expiry Board", forecast: "Forecast Explorer",
    transfers: "Transfer Desk", alerts: "Alerts", stress: "Stress Test", copilot: "Copilot", eval: "Evaluation",
    quality: "Data Quality", register: "Snap Register", donors: "Donor Appeals", inventory: "Record Stock",
    critical: "Critical", high: "High", medium: "Medium", low: "Low", logout: "Sign out", approve: "Approve",
    reject: "Reject", dispatch: "Dispatch", receive: "Receive", cancel: "Cancel", why: "Why?",
    synthetic: "Synthetic demo data", decision: "Decision support only - humans approve every transfer",
    tts: "Time to stockout", p24: "Stockout in 24 h", units: "units", asof: "as of", articles: "Articles", access: "Access requests",
  },
  hi: {
    command: "कमांड सेंटर", map: "जोखिम मानचित्र", matrix: "उपलब्धता", expiry: "एक्सपायरी बोर्ड", forecast: "पूर्वानुमान",
    transfers: "ट्रांसफर डेस्क", alerts: "अलर्ट", stress: "स्ट्रेस टेस्ट", copilot: "कोपायलट", eval: "मूल्यांकन",
    quality: "डेटा गुणवत्ता", register: "रजिस्टर स्कैन", donors: "रक्तदाता अपील", inventory: "स्टॉक दर्ज करें",
    critical: "गंभीर", high: "उच्च", medium: "मध्यम", low: "कम", logout: "साइन आउट", approve: "स्वीकृत करें",
    reject: "अस्वीकार", dispatch: "रवाना करें", receive: "प्राप्त करें", cancel: "रद्द करें", why: "यह योजना क्यों?",
    synthetic: "सिंथेटिक डेमो डेटा", decision: "केवल निर्णय सहायता - हर ट्रांसफर मानव स्वीकृत करता है",
    tts: "स्टॉक खत्म होने का समय", p24: "24 घंटे में कमी", units: "यूनिट", asof: "तक", articles: "लेख", access: "पहुँच अनुरोध",
  },
};
export type Lang = keyof typeof dict;
export type Key = keyof typeof dict.en;
export type I18nValue = { lang: Lang; setLang: (l: Lang) => void; t: (k: Key) => string };

export const I18n = createContext<I18nValue>(null as never);
export const useI18n = () => useContext(I18n);
