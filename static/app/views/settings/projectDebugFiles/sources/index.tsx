import {Fragment} from 'react';
import {type InjectedRouter} from 'react-router';
import {type Location} from 'history';

import {type Client} from 'sentry/api';
import {type Organization, type Project} from 'sentry/types';
import {type BuiltinSymbolSource, type CustomRepo} from 'sentry/types/debugFiles';

import BuiltInRepositories from './builtInRepositories';
import CustomRepositories from './customRepositories';

type Props = {
  api: Client;
  builtinSymbolSourceOptions: BuiltinSymbolSource[];
  builtinSymbolSources: string[];
  customRepositories: CustomRepo[];
  isLoading: boolean;
  location: Location;
  organization: Organization;
  projSlug: Project['slug'];
  router: InjectedRouter;
};

function Sources({
  api,
  organization,
  customRepositories,
  builtinSymbolSources,
  builtinSymbolSourceOptions,
  projSlug,
  location,
  router,
  isLoading,
}: Props) {
  return (
    <Fragment>
      <BuiltInRepositories
        api={api}
        organization={organization}
        builtinSymbolSources={builtinSymbolSources}
        builtinSymbolSourceOptions={builtinSymbolSourceOptions}
        projSlug={projSlug}
        isLoading={isLoading}
      />
      <CustomRepositories
        api={api}
        location={location}
        router={router}
        organization={organization}
        customRepositories={customRepositories}
        projSlug={projSlug}
        isLoading={isLoading}
      />
    </Fragment>
  );
}

export default Sources;
