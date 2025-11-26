import type { AppProps } from "next/app";
import "mapbox-gl/dist/mapbox-gl.css";
import "../global.css";

export default function App({ Component, pageProps }: AppProps) {
  return <Component {...pageProps} />;
}
