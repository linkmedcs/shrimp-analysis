import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link className="brand" href="/">
          <span className="brand__mark">LV</span>
          <span>
            <strong>对虾种质数据库</strong>
            <small>Litopenaeus vannamei</small>
          </span>
        </Link>
        <nav className="site-nav" aria-label="主导航">
          <Link className="site-nav__active" href="/">
            种质鉴定
          </Link>
          <span className="site-nav__disabled" title="后续阶段开放">
            分子指纹 <em>规划中</em>
          </span>
        </nav>
      </div>
    </header>
  );
}
