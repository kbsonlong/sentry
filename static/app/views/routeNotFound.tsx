import {useEffect} from 'react';
import {type RouteComponentProps} from 'react-router';
import * as Sentry from '@sentry/react';

import NotFound from 'sentry/components/errors/notFound';
import Footer from 'sentry/components/footer';
import SentryDocumentTitle from 'sentry/components/sentryDocumentTitle';
import Sidebar from 'sentry/components/sidebar';
import {t} from 'sentry/locale';

type Props = RouteComponentProps<{}, {}>;

function RouteNotFound({router, location}: Props) {
  const {pathname, search, hash} = location;

  const isMissingSlash = pathname[pathname.length - 1] !== '/';

  useEffect(() => {
    // Attempt to fix trailing slashes first
    if (isMissingSlash) {
      router.replace(`${pathname}/${search}${hash}`);
      return;
    }

    Sentry.withScope(scope => {
      scope.setFingerprint(['RouteNotFound']);
      Sentry.captureException(new Error('Route not found'));
    });
  }, [pathname, search, hash, isMissingSlash, router]);

  if (isMissingSlash) {
    return null;
  }

  return (
    <SentryDocumentTitle title={t('Page Not Found')}>
      <div className="app">
        <Sidebar location={location} />
        <div className="container">
          <div className="content">
            <section className="body">
              <NotFound />
            </section>
          </div>
        </div>
        <Footer />
      </div>
    </SentryDocumentTitle>
  );
}

export default RouteNotFound;
