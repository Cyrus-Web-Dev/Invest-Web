import Icon from "./icons";

export default function Splash() {
  return (
    <div className="splash" aria-busy="true" aria-label="Memuat aplikasi">
      <span className="logo splash-logo"><Icon name="activity" size={26} /></span>
      <div className="splash-name">Stockfolio</div>
    </div>
  );
}
