function varargout = uscounty(varargin)
%USCOUNTY US county data.
%      s = uscounty          Output all variables as structure 's'
%[x1,x2] = uscounty          Output only first 1, 2, etc., variables
%      s = uscounty('x',...) Output only variables 'x', ... as str. 's'
%[x,...] = uscounty('x',...) Output variables 'x', ... as variables
%        = uscounty(...,is)  Output subset x(is) using SUBSETSTUCT(s,is)
%                               where 'is' is vector of elements to extract
%
% Loads data file "uscounty.mat" that contain the following variables:
%        SCfips = m-element vector of state and 3-digit county FIPS codes
%          Name = m-element cell array of county names
%            ST = m-element cell array of m 2-char state abbreviations
%            XY = m x 2 matrix of county pop center lon-lat (in dec deg)
%           Pop = m-element vector of total population estimates (2010)
%      LandArea = m-element vector of land area (square miles)
%     WaterArea = m-element vector of water area (square miles)
%      CBSAcode = m-element vector of CBSA Code
%  MetroDivCode = m-element vector of Metropolitan Division Code
%       CSAcode = m-element vector of CSA Code
%     CBSAtitle = m-element cell array of CBSA Title
% Metro_MicroSA = m-element cell array of Metropolitan/Micropolitan 
%                 Statistical Area
% MetroDivTitle = m-element cell array of Metropolitan Division Title
%      CSAtitle = m-element cell array of CSA Title
% Central_Outly = m-element cell array of Central/Outlying County
%
% Example: Plot all counties in California
% CA = uscounty(mor('CA',uscounty('ST')))
% % CA = 
% %        SCfips: [1x58 double]
% %          Name: {1x58 cell}
% %            ST: {1x58 cell}
% %            XY: [58x2 double]
% %           Pop: [1x58 double]
% %      LandArea: [1x58 double]
% %     WaterArea: [1x58 double]
% %      CBSAcode: [1x58 double]
% %  MetroDivCode: [1x58 double]
% %       CSAcode: [1x58 double]
% %     CBSAtitle: {1x58 cell}
% % Metro_MicroSA: {1x58 cell}
% % MetroDivTitle: {1x58 cell}
% %      CSAtitle: {1x58 cell}
% % Central_Outly: {1x58 cell}
% makemap(CA.XY)
% pplot(CA.XY,'r.')
% pplot(CA.XY,CA.Name)
%
% XY, Pop, LandArea, and WaterArea for each county derived from US census
% block group data in USCENBLKGRP. County Name, ST, and SCfips from 
% http://www2.census.gov/geo/docs/reference/codes/files/national_county.txt
%
% CBSAs, Metropolitan Divisions, and CSAs data from https://www.census.gov/
% geographies/reference-files/time-series/demo/metro-micro/delineation-
% files.html and https:https://www2.census.gov/programs-surveys/metro-
% micro/geographies/reference-files/2020/delineation-files/list1_2020.xls

% Copyright (c) 1994-2016 by Michael G. Kay
% Matlog Version 17 03-Jul-2020 (http://www.ise.ncsu.edu/kay/matlog)

% Input Error Checking ****************************************************
varnames = {'SCfips','Name','ST','XY','Pop','LandArea','WaterArea',...
   'CBSAcode','MetroDivCode','CSAcode','CBSAtitle','Metro_MicroSA',...
   'MetroDivTitle','CSAtitle','Central_Outly'};
[errstr,varargout] = loaddatafile(varargin,nargout,varnames,mfilename);
if ~isempty(errstr), error(errstr), end
% End (Input Error Checking) **********************************************
