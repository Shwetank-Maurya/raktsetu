import { useState, type ReactNode } from "react";
import { dict, I18n, type Lang } from "./i18n-context";

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>((localStorage.getItem("raktsetu.lang") as Lang) || "en");
  const setLang = (l: Lang) => {
    localStorage.setItem("raktsetu.lang", l);
    document.documentElement.lang = l;
    setLangState(l);
  };
  return <I18n.Provider value={{ lang, setLang, t: (k) => dict[lang][k] ?? dict.en[k] }}>{children}</I18n.Provider>;
}
