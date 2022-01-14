function shagg = aggshmt(sh,dof)
%AGGSHMT Aggregate multiple shipments.
% shagg = aggshmt(sh)
%       = aggshmt(sh,dof)
%    sh = structure array with fields:
%       .f = annual demand (tons/yr)
%       .q = single shipment weight (tons)
%       .s = shipment density (lb/ft^3)
%       .v = shipment value ($/ton)
%       .h = annual holding cost fraction (1/yr)
%       .a = inventory 0-D fraction
%   dof = use "f" unless field missing = true, default
% shagg = single aggregate structure
%
% Note: 1. Aggregation based on "f" values unless "f" field is missing or
%          empty, in which case it is based on "q" values.
%       2. Aggregate field determined for "f", "s", "a", "v", and "h" 
%          only if respective fields are present in each shipment
%       3. All other fields are passed to aggregate shipment based on
%          their values in the first input shipment structure sh(1)

% Copyright (c) 1994-2016 by Michael G. Kay
% Matlog Version 17 09-Aug-2017 (http://www.ise.ncsu.edu/kay/matlog)

% Input Error Checking ****************************************************
narginchk(1,2)

if nargin < 2 || isempty(dof), dof = true; end

if ~isstruct(sh)
   error('Input must be a shipment structure.')
elseif dof && ~isfield(sh,'f')
   error('Shipments must have field "f".')
elseif ~dof && ~isfield(sh,'q')
   error('Shipments must have field "q".')
elseif ~isscalar(dof) || (~islogical(dof) && ~any(dof == [0 1]))
   error('Second argument must be a logical scalar.')
end
% End (Input Error Checking) **********************************************

shagg = sh(1);
if (~dof || ~isfield(sh,'f') || isempty(shagg.f)) ...
      && isfield(sh,'q') && ~isempty(shagg.q)
   x = [sh.q];
   shagg.q = sum(x);
elseif dof && isfield(sh,'f') && ~isempty(shagg.f)
   x = [sh.f];
   shagg.f = sum(x);
end
if isfield(sh,'s')
   shagg.s = sum(x)/sum(x./[sh.s]);
end
if isfield(sh,'v')
   shagg.v = sum((x/sum(x)).*[sh.v]);
end
if isfield(sh,'h')
   shagg.h = sum((x/sum(x)).*[sh.h]);
end
if isfield(sh,'a')
   shagg.a = sum((x/sum(x)).*[sh.a]);
end
