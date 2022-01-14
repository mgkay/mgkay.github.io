function varargout = uscenblkgrp(varargin)
%USCENBLKGRP US census block group data.
%      s = uscenblkgrp          Output all variables as structure 's'
%[x1,x2] = uscenblkgrp          Output only first 1, 2, etc., variables
%      s = uscenblkgrp('x',...) Output only variables 'x', ... as str. 's'
%[x,...] = uscenblkgrp('x',...) Output variables 'x', ... as variables
%        = uscenblkgrp(...,is)  Output subset x(is) using SUBSETSTUCT(s,is)
%                               where 'is' is vector of elements to extract
%
% Loads data file "uscenblkgrp.mat" that contain the following variables:
%         ST = m-element cell array of m 2-char state abbreviations
%         XY = m x 2 matrix of block-group pop center lon-lat (in dec deg)
%        Pop = m-element vector of total population estimates (2010)
%   LandArea = m-element vector of land area (square miles)
%  WaterArea = m-element vector of water area (square miles)
%     SCfips = m-element vector of state and 3-digit county FIPS codes
%TractBlkGrp = m-element vector of tract and 1-digit block-group codes,
%              where the block-group code is the leftmost digit of the
%              4-digit block codes of the blocks that comprise the group
%
% Example: Plot all census tracts in Raleigh-Durham-Cary, NC
% %        Combined Statistical Area
% [SCfips,Name,str] = uscounty('SCfips','Name','CSAtitle',...
%    mor({'raleigh'},uscounty('CSAtitle')));
% str = [str{1} ' CSA'];
% mdisp(SCfips',Name,{'SCfips'},str)
% x = uscenblkgrp(mor(SCfips,uscenblkgrp('SCfips')));
% makemap(x.XY), pplot(x.XY,'r.'), title(str)
% %  
% % Raleigh-Durham-Cary, NC CSA:  SCfips
% % ---------------------------:--------
% %                     Chatham:  37,037
% %                      Durham:  37,063
% %                    Franklin:  37,069
% %                   Granville:  37,077
% %                    Johnston:  37,101
% %                      Orange:  37,135
% %                      Person:  37,145
% %                       Vance:  37,181
% %                        Wake:  37,183
%
% Sources:
% [1] http://www.census.gov/geo/www/2010census/centerpop2010/blkgrp/bgcenters.html
%     (file: .../blkgrp/CenPop2010_Mean_BG.txt)
% [2] http://www.census.gov/geo/www/2010census/rel_blk_layout.html
%     (all files in: ...2010census/t00t10.html)
%
%  Block-group data derived from US Census Bureau's 2010 Census Centers of
%  Population by Census Block Group data (file [1]) and Census 2000
%  Tabulation Block to 2010 Census Tabulation Block data (files in [2]).
%  File [1] used for ST, XY, Pop, SCfips, and TractBlkGrp, where ST is
%  converted to alpha from numeric FIPS codes using FIPSNUM2ALPHA. Files in
%  [2] used for LandArea and WaterArea.

% Copyright (c) 1994-2016 by Michael G. Kay
% Matlog Version 17 26-Jul-2020 (http://www.ise.ncsu.edu/kay/matlog)

% Input Error Checking ****************************************************
varnames = {'ST','XY','Pop','LandArea','WaterArea','SCfips','TractBlkGrp'};
[errstr,varargout] = loaddatafile(varargin,nargout,varnames,mfilename);
if ~isempty(errstr), error(errstr), end
% End (Input Error Checking) **********************************************
