import styles from '../DownloadPage.module.css';

export default function Header() {
  return (
    <>
      <div className={styles.logoRow}>
        <a href="https://github.com/freemocap/skellycam" title="SkellyCam on GitHub">
          <img
            className={styles.logoImg}
            src="https://raw.githubusercontent.com/freemocap/skellycam/development/shared/skellycam-logo/skellycam-logo.png"
            alt="SkellyCam logo"
          />
        </a>
        <h1 className={styles.title}>
          Skelly<span className={styles.titleAccent}>Cam</span>
        </h1>
      </div>

      <p className={styles.tagline}>
        The camera backend for the{' '}
        <a href="https://freemocap.org">FreeMoCap</a> project. An easy and
        efficient way to connect to one or more cameras and record synchronized
        videos.
      </p>

      <div className={styles.repoLinks}>
        <a href="https://github.com/freemocap/skellycam">GitHub</a>
        <span className={styles.repoSep}>&middot;</span>
        <a href="https://github.com/freemocap/skellycam/releases">
          Release Notes
        </a>
        <span className={styles.repoSep}>&middot;</span>
        <a href="https://github.com/freemocap/skellycam/blob/development/LICENSE">
          AGPL-3.0
        </a>
      </div>
    </>
  );
}
