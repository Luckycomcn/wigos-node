import { createApp } from "vue";
import App from "./App.vue";
import vuetify from "./plugins/vuetify";
import i18n from "./i18n";
import "leaflet/dist/leaflet.css";
import "./app.css";

createApp(App).use(i18n).use(vuetify).mount("#app");
