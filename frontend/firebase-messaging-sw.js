// firebase-messaging-sw.js
importScripts('https://www.gstatic.com/firebasejs/10.12.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.1/firebase-messaging.js');

firebase.initializeApp({
  apiKey: "AIzaSyBnVyOV94TbBGw5NvSSdplMBm_jGBCQMrY",
  authDomain: "todo-list-e8834.firebaseapp.com",
  projectId: "todo-list-e8834",
  storageBucket: "todo-list-e8834.firebasestorage.app",
  messagingSenderId: "900155232272",
  appId: "1:900155232272:web:da8b6372d97e0073cdba95",
  measurementId: "G-M8M13BEXPX"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage(payload => {
  console.log('Background message received: ', payload);
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/icon.png' // optional icon path
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});
