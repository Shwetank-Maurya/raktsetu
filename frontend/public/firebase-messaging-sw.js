/* Firebase Cloud Messaging service worker: shows High/Critical alert pushes when the tab is closed.
   The public web config arrives via the registration URL (?config=...) so nothing is hard-coded. */
importScripts("https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js");
const cfg = JSON.parse(new URL(self.location).searchParams.get("config") || "{}");
if (cfg.apiKey) {
  firebase.initializeApp(cfg);
  firebase.messaging().onBackgroundMessage((payload) => {
    const n = payload.notification || {};
    self.registration.showNotification(n.title || "RaktSetu alert", { body: n.body, icon: "/favicon.svg", tag: payload.data && payload.data.alert_id });
  });
}
