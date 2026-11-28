/* Asset governance explorer, public edition. Generated from a working version; see docs/explorer.md. */
{
const META={version:'2.3.0',reviewed:'2026-11-16',nextReview:'2026-12-17'};
const SMOOTH=()=>document.documentElement.classList.contains('d-rm')||matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth';
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const OBJ=[];
const DCL={D1:'Direction and oversight',D2:'Core DAM capabilities',D3:'Data management enablers',D4:'Protection, ethics and trust',D5:'People and culture',D6:'Delivery, change and value'};
const ICL={C1:'Direction and oversight',C2:'Core information asset capabilities',C3:'Lifecycle: create to preserve or destroy',C4:'Access, rights and protection',C5:'Knowledge management',C6:'Platforms and channels',C7:'People and culture',C8:'Delivery, change and value'};
const FLAG={E:'Explicit',I:'Implicit',N:'Inferred'};
const REL={shared:'Shared',adapt:'Needs an information version',data:'Data only',gap:'Gap: information only'};

// id, name, DAM cluster, flag, relationship, info cluster, information-world counterpart, GKIM work, objectives
const CAPS=[
['CR-01','Accountable leadership and policy oversight','D1','E','shared','C1','Senior information risk owner, information asset owners and KIM Leaders alongside the CDO','',[]],
['CR-02','Data strategy and prioritisation by reuse value','D1','I','adapt','C1','Information strategy that treats information as a strategic asset','',[]],
['CR-03','Central reporting, assurance and arm\'s length body coordination','D1','E','adapt','C1','KIM self-assessment returns; TNA Information Management Assessments','',[]],
['CR-04','Performance measurement and annual review','D1','E','adapt','C1','Section 46 Code maturity assessment and KIM self-assessment analysis','',[]],
['CR-05','Identify and scope critical data assets','D2','E','adapt','C2','Identify information assets and record series of enduring value','',[]],
['CR-06','Data cataloguing and metadata management','D2','E','shared','C2','Information asset register and records metadata','',[]],
['CR-07','Data ownership and stewardship','D2','E','shared','C2','Information asset owners and managers alongside data owners and stewards','',[]],
['CR-08','Data quality management through action plans','D2','E','data','','Information counterpart is authenticity and integrity of records (see IM-12)','',[]],
['CR-09','Data quality issue management','D2','I','data','','No direct counterpart','',[]],
['CR-10','Data life cycle management','D3','E','adapt','C3','Records lifecycle from creation to preservation or destruction','',[]],
['CR-11','Interoperability, data standards and identifiers','D3','E','data','','Mostly data; records use file plans and records metadata instead','',[]],
['CR-12','Data architecture and data services','D3','I','data','','Information counterpart is information architecture (see IM-02)','',[]],
['CR-13','Catalogue and quality tooling','D3','I','shared','C6','The same platforms hold records and labels (for example Microsoft Purview)','',[]],
['CR-14','Reference data, master data and authoritative sources','D3','I','data','','No direct counterpart','',[]],
['CR-15','Records, retention and disposal','D3','N','adapt','C3','Core of information asset management, inferred only in the DAM Policy','',[]],
['CR-16','Security classification and protective controls','D4','E','shared','C4','Classification and handling of all information assets','',[]],
['CR-17','Data protection and lawful sharing','D4','E','shared','C4','Records of processing activities and sharing agreements','',[]],
['CR-18','AI readiness and data and AI ethics','D4','E','shared','C4','Is information known, owned, described and lawful to use with AI','',[]],
['CR-19','Data risk management','D4','E','shared','C4','Information risk registers and baselines','',[]],
['CR-20','Third-party and supplier data','D4','I','shared','C4','Information held by service providers','',[]],
['CR-21','Data skills, capability and literacy','D5','I','shared','C7','Information management skills and training','',[]],
['CR-22','Data culture and engagement with users','D5','I','shared','C7','KIM community and engagement','',[]],
['CR-23','Maturity assessment and continuous improvement','D5','I','shared','C7','KIM self-assessment alongside the Data Maturity Assessment','',[]],
['CR-24','Investment, business cases and value','D6','E','adapt','C8','The value of information as a strategic asset','',[]],
['CR-25','Integration with programmes, spend control and assurance','D6','N','shared','C8','KIM built into project delivery','',[]],
['CR-26','Legacy migration and decommissioning','D6','N','adapt','C3','Migrate records with their evidential value and metadata intact','',[]],
['CR-27','Ownership transition and handover to business as usual','D6','I','shared','C8','Transfer of information asset owner roles','',[]],
['CR-28','Cross-boundary collaboration','D6','E','shared','C8','Sharing across organisations and machinery of government changes','',[]],
['CR-29','Benefits realisation and evaluation','D6','N','shared','C8','Benefits of managed information','',[]],
['CR-30','Equality and inclusion in data','D4','N','data','','No direct counterpart','',[]],
['CR-31','Cyber resilience and incident response for data assets','D4','I','shared','C4','Incident response for information assets','',[]],
['CR-32','Avoiding future legacy: open standards, portability and exit','D6','N','adapt','C3','Formats and exit plans that keep records usable','',[]]
].map(a=>({id:a[0],name:a[1],dc:a[2],flag:a[3],rel:a[4],ic:a[5],info:a[6],gkim:a[7],obj:a[8]}));

const GAPS=[
['IM-01','Records capture and declaration','C3','Capture records of business activity in managed places','Set capture rules for email and chat','Declare a decision email as a record in its file plan location','Section 46 Code; ISO 15489-1','',[]],
['IM-02','Business classification scheme and information architecture','C2','Maintain the file plan','Map a directorate\'s functions to plan headings','Add a heading with its owner and retention rule','ISO 15489-1; ARMA IGIM (structures)','',[]],
['IM-03','Retention schedules and disposal','C3','Apply the retention schedule','Disposal review of a record series','Check there is no hold or moratorium, then log the decision, authority, date and evidence','Section 46 Code; ISO 15489-1','',[]],
['IM-04','Appraisal and selection','C3','Appraise records for historical value','Apply the selection policy to a series','Record a select or destroy decision with its rationale','Public Records Act 1958; TNA Digital ASSR tool','',[]],
['IM-05','Sensitivity review and transfer to The National Archives','C3','Review and transfer selected records','Sensitivity-review a batch due for transfer','Flag a closure request with its justification','Public Records Act 1958; TNA Digital ASSR tool','',[]],
['IM-06','Digital preservation and continuity','C3','Keep records usable across system change','Check formats in a store at risk','Migrate a file to a preservation format and log its checksum','ISO 14721 (OAIS)','',[]],
['IM-07','FOI, EIR and subject access readiness','C4','Find and retrieve information for requests','Search a business area\'s stores for a request','Log where each item was found and why anything was withheld','Freedom of Information Act 2000; Section 46 Code','',[]],
['IM-08','Legal holds, inquiries and investigations','C4','Preserve information under a hold or moratorium','Apply a hold to the stores in scope','Suspend disposal for a series and record who authorised it','Section 46 Code','',[]],
['IM-09','Knowledge capture and corporate memory','C5','Capture knowledge before people move on','Run a leaver handover','Record where key files live and who to ask','ISO 30401','',[]],
['IM-10','Findability and search','C5','Make information findable','Set metadata and search for a site','Add required metadata fields to a document library','ISO 23081-1','',[]],
['IM-11','Collaboration platform governance and the digital heap','C6','Govern Microsoft 365 and shared drives','Remediate a legacy shared drive','Mark a folder for disposal, migration or retention','TNA M365 maturity tool (IMA toolkit)','',[]],
['IM-12','Authenticity, integrity and evidential value','C2','Keep records trustworthy as evidence','Control edits to declared records','Lock a declared record and keep its audit trail','ISO 15489-1; ISO 23081-1','',[]],
['IM-13','AI prompts, outputs and agent actions as records','C6','Treat AI interactions as information','Decide which AI outputs are records','Capture an AI-assisted decision with its prompt and sources','ISO/IEC 42001 (A.7 data for AI); AI Playbook for the UK Government','',[]]
].map(a=>({id:a[0],name:a[1],ic:a[2],proc:a[3],act:a[4],unit:a[5],src:a[6],gkim:a[7],obj:a[8],rel:'gap'}));

const JOINS=[];
const OTHERS=[];

const TL=[];

const ROLES={};

// Standards: id, name, type, domains, what it is, verified fact, status, url, covers {theme:2 core|1 touches}
const STD=[
{id:'DMBOK',name:'DAMA-DMBOK2',type:'Body of knowledge',dom:['D'],what:'DAMA International\'s reference framework for data management. The DAM playbooks are built on its wheel.',fact:'11 knowledge areas with data governance at the hub. A 2024 maintenance revision left the knowledge areas unchanged.',status:'Current (DMBOK2, 2024 revision)',url:'https://www.dawiso.com/glossary/dama-dmbok',cov:{own:2,inv:1,meta:2,life:1,qual:2,sec:2,arch:2,mat:0,know:1,ai:0,pres:0,evid:0}},
{id:'DCAM',name:'EDM Council DCAM',type:'Maturity model',dom:['D'],what:'A data management capability assessment model with scoring against auditable evidence.',fact:'Eight components; 38 capabilities and 136 sub-capabilities. Version 3 is current. Available to EDM Council members.',status:'Current (v3)',url:'https://edmcouncil.org/',cov:{own:2,inv:1,meta:2,life:1,qual:2,sec:1,arch:2,mat:2,know:0,ai:1,pres:0,evid:0}},
{id:'DMM',name:'CMMI Data Management Maturity (DMM)',type:'Maturity model',dom:['D'],what:'A process-area maturity model for data management.',fact:'Six categories and 25 process areas. ISACA discontinued it in January 2022 and folded selected content into CMMI.',status:'Retired; content partly in CMMI v3',url:'https://tdan.com/?p=30607',cov:{own:2,inv:0,meta:2,life:1,qual:2,sec:0,arch:2,mat:2,know:0,ai:0,pres:0,evid:0}},
{id:'DMA',name:'Data Maturity Assessment for Government',type:'Maturity model',dom:['D'],what:'The UK government self-assessment framework for data maturity.',fact:'10 topics across 6 themes in 97 rows, each with 5 maturity levels. Published 27 March 2023.',status:'Current (UK government)',url:'https://www.gov.uk/government/publications/data-maturity-assessment-for-government-framework/data-maturity-assessment-for-government-framework-html',cov:{own:1,inv:2,meta:1,life:1,qual:2,sec:1,arch:1,mat:2,know:1,ai:1,pres:0,evid:0}},
{id:'38505',name:'ISO/IEC 38505-1',type:'Standard',dom:['D'],what:'Applies the ISO/IEC 38500 governance model to the governance of data, for governing bodies.',fact:'The second edition was published in August 2026 and replaces the 2017 edition.',status:'Current (2026)',url:'https://www.iso.org/standard/87195.html',cov:{own:2,inv:0,meta:0,life:1,qual:0,sec:1,arch:0,mat:0,know:0,ai:0,pres:0,evid:0}},
{id:'15489',name:'ISO 15489-1',type:'Standard',dom:['I'],what:'The concepts and principles of records management.',fact:'Covers records, metadata for records and records systems; responsibilities; records controls; and processes to create, capture and manage records. Reviewed and confirmed in 2021.',status:'Current (2016, confirmed 2021)',url:'https://www.iso.org/standard/62542.html',cov:{own:2,inv:1,meta:2,life:2,qual:1,sec:1,arch:1,mat:0,know:0,ai:0,pres:1,evid:2}},
{id:'23081',name:'ISO 23081-1',type:'Standard',dom:['I'],what:'Principles for records management metadata.',fact:'The 2017 edition is aligned with ISO 15489-1:2016.',status:'Current (2017)',url:'https://committee.iso.org/sites/tc46sc11/home/news/content-left-area/news-about-standarization-in-t-1/iso-23081-1-records-management-p.html',cov:{own:1,inv:1,meta:2,life:2,qual:0,sec:1,arch:1,mat:0,know:0,ai:0,pres:1,evid:2}},
{id:'30301',name:'ISO 30301',type:'Standard',dom:['I'],what:'Requirements for a management system for records, certifiable like ISO 9001.',fact:'The 2019 edition follows the common management-system structure. A third edition is in draft.',status:'Current (2019); revision in progress',url:'https://committee.iso.org/standard/74292.html',cov:{own:2,inv:1,meta:1,life:2,qual:0,sec:1,arch:0,mat:1,know:0,ai:0,pres:1,evid:2}},
{id:'OAIS',name:'ISO 14721 (OAIS)',type:'Reference model',dom:['I'],what:'The reference model for an archive that preserves information for the long term.',fact:'Third edition published March 2025.',status:'Current (2025)',url:'https://www.iso.org/standard/87471.html',cov:{own:0,inv:0,meta:2,life:1,qual:0,sec:0,arch:1,mat:0,know:0,ai:0,pres:2,evid:1}},
{id:'IGIM',name:'ARMA Information Governance Implementation Model',type:'Maturity model',dom:['I'],what:'An implementation-focused information governance model with an annual maturity index.',fact:'Seven key areas; ARMA\'s Information Governance Maturity Index survey is aligned to it.',status:'Current',url:'https://magazine.arma.org/2019/12/introducing-the-information-governance-maturity-model-igim/',cov:{own:2,inv:1,meta:1,life:2,qual:0,sec:2,arch:2,mat:2,know:0,ai:0,pres:1,evid:1}},
{id:'30401',name:'ISO 30401',type:'Standard',dom:['K'],what:'Requirements for a knowledge management system.',fact:'Published in 2018; a second edition is in draft.',status:'Current (2018); revision in progress',url:'https://www.iso.org/contents/data/standard/06/86/68683.html',cov:{own:1,inv:0,meta:0,life:0,qual:0,sec:0,arch:0,mat:1,know:2,ai:0,pres:0,evid:0}},
{id:'27001',name:'ISO/IEC 27001 control 5.9',type:'Standard',dom:['D','I'],what:'The information security control requiring an inventory of information and associated assets.',fact:'An inventory of information and other associated assets, including owners, is developed and maintained.',status:'Current (2022)',url:'https://advisera.com/27001academy/knowledgebase/how-to-handle-asset-register-asset-inventory-according-to-iso-27001/',cov:{own:2,inv:2,meta:0,life:1,qual:0,sec:2,arch:0,mat:0,know:0,ai:0,pres:0,evid:0}},
{id:'DCAT',name:'W3C DCAT 3',type:'Standard',dom:['D'],what:'The RDF vocabulary for describing datasets and data services in catalogues. The base of the cross-government Metadata Exchange Model.',fact:'W3C Recommendation, 22 August 2024; adds dataset series and versioning.',status:'Current (2024)',url:'https://www.w3.org/TR/vocab-dcat-3/',cov:{own:1,inv:2,meta:2,life:1,qual:0,sec:1,arch:1,mat:0,know:0,ai:0,pres:0,evid:0}},
{id:'42001',name:'ISO/IEC 42001',type:'Standard',dom:['A'],what:'Requirements for an AI management system.',fact:'Published 2023; its controls include data for AI systems, covering data quality and provenance.',status:'Current (2023)',url:'https://store.standards.org.au/product/as-iso-iec-42001-2023',cov:{own:2,inv:1,meta:1,life:1,qual:2,sec:1,arch:0,mat:0,know:0,ai:2,pres:0,evid:0}},
{id:'NIST',name:'NIST AI Risk Management Framework',type:'Framework',dom:['A'],what:'Voluntary guidance for managing AI risk.',fact:'Released 26 January 2023; four functions: Govern, Map, Measure and Manage.',status:'Current (1.0)',url:'https://airc.nist.gov/airmf-resources/airmf/0-ai-rmf-1-0',cov:{own:2,inv:1,meta:0,life:1,qual:1,sec:1,arch:0,mat:0,know:0,ai:2,pres:0,evid:0}},
{id:'AIPB',name:'AI Playbook for the UK Government and ATRS',type:'UK government',dom:['A'],what:'UK government guidance for using AI, and the standard for publishing records of algorithmic tools.',fact:'The AI Playbook was published in February 2025; ATRS records are mandatory for central government departments and in-scope arm\'s length bodies.',status:'Current (UK government)',url:'https://www.gov.uk/government/publications/algorithmic-transparency-recording-standard-mandatory-scope-and-exemptions-policy',cov:{own:1,inv:2,meta:1,life:0,qual:1,sec:1,arch:0,mat:0,know:0,ai:2,pres:0,evid:0}},
{id:'TNA',name:'TNA Information Management Assessment toolkit',type:'UK government',dom:['I'],what:'Independent assessments and maturity tools from The National Archives.',fact:'Includes a Section 46 Maturity Assessment Tool, a Digital ASSR Maturity Assessment Tool developed with the GKIM community, and an M365 tool.',status:'Current (UK government)',url:'https://www.nationalarchives.gov.uk/information-management/manage-information/ima/',cov:{own:1,inv:1,meta:1,life:2,qual:0,sec:1,arch:1,mat:2,know:1,ai:0,pres:2,evid:2}},
{id:'S46',name:'Section 46 Code of Practice',type:'UK government',dom:['I'],what:'The Lord Chancellor\'s code on managing records under the Freedom of Information Act.',fact:'A technical document supporting the management of public authority records and information.',status:'Current (UK government)',url:'https://www.nationalarchives.gov.uk/information-management/legislation/section-46/',cov:{own:2,inv:1,meta:1,life:2,qual:0,sec:1,arch:1,mat:0,know:0,ai:0,pres:1,evid:2}}
];
const THEMES=[['own','Ownership and accountability'],['inv','Inventory or register of assets'],['meta','Metadata and description'],['life','Lifecycle, retention and disposal'],['qual','Quality and fitness for use'],['sec','Security, access and protection'],['arch','Architecture and structures'],['mat','Maturity assessment'],['know','Knowledge and tacit know-how'],['ai','AI-specific governance'],['pres','Long-term preservation'],['evid','Evidential value and authenticity']];
const UNIQ=[['D','Unique to data','Master and reference data, data modelling and integration, statistical data quality dimensions, data architecture and APIs.'],['I','Unique to information and records','Evidential value and authenticity, appraisal and selection, sensitivity review and transfer, retention and disposal schedules, long-term preservation, FOI readiness.'],['K','Unique to knowledge','Tacit knowledge, communities of practice, lessons learned and corporate memory.'],['A','Unique to AI','Impact assessment of AI systems, model lifecycle, provenance of training data, transparency records such as ATRS.']];

// IAR field, DCAT term, records metadata type, standard served, fit (core | extension | IAR-only)
const XW=[
['Asset ID','dct:identifier','Identity metadata about the record','ISO/IEC 27001 5.9; DCAT 3','core'],
['Asset name','dct:title','Description metadata about the record','DCAT 3; ISO 23081-1','core'],
['Description','dct:description','Description metadata about the record','DCAT 3; ISO 23081-1','core'],
['Directorate','dct:publisher (organisation) with prov:qualifiedAttribution for the business area','Metadata about the responsible agent','DCAT 3; ISO 15489-1','core'],
['Information asset owner (IAO)','prov:qualifiedAttribution with dcat:hadRole (owner)','Metadata about the responsible agent','ISO/IEC 27001 5.9; an information accountability model','core'],
['Information asset manager (IAM)','prov:qualifiedAttribution with dcat:hadRole (custodian); dcat:contactPoint','Metadata about the responsible agent','DAM Data Ownership Model','core'],
['Location or system','dcat:distribution, dcat:accessService','Metadata about the system the record resides in','DCAT 3; ISO 23081-1','core'],
['Security classification','dct:accessRights','Security metadata','Government Security Classifications; ISO/IEC 27001','core'],
['Access and sharing','dct:accessRights, dct:license, odrl:hasPolicy','Accessibility metadata','DCAT 3; UK GDPR sharing','core'],
['Personal data','No DCAT core term','Security metadata','UK GDPR records of processing','extension'],
['Retention','No DCAT core term','Metadata about records management processes (disposal)','Section 46 Code; ISO 15489-1','extension'],
['Business criticality','No DCAT core term (DAM critical data asset flag)','Not covered','DAM Policy','extension'],
['Risk rating','No DCAT core term','Not covered','information risk assessment','IAR-only'],
['Last review date','dct:modified (closest match)','Metadata about records management processes','ISO/IEC 27001 5.9 (keep current)','core'],
['Next review date','No DCAT core term','Metadata about records management processes','ISO/IEC 27001 5.9 (keep current)','IAR-only']
];

const GLOSS=[
['BAU','Business as usual: running and improving today\'s arrangements.','B'],
['Change','Programmes, reforms and new arrangements being introduced; the opposite lens to business as usual.','B'],
['Lens','A filter at the top of the page that narrows tagged items to business as usual or change, and to evolution, reform or revolution.','B'],
['Persona','An illustrative reader built from the roles in this resource, used to test whether it meets their needs.','B'],
['Journey','One persona\'s route through the resource, from getting oriented to reviewing the result.','B'],
['Pathway','A task route through several views, with a trail showing the current step.','B'],
['Wayfinder','Three questions that suggest the closest persona and a pathway.','B'],
['ECM','Enterprise content management: governing documents and content across the platforms where they are created and kept.','I'],
['Information wheel','This page\'s reference model for knowledge, information, records and content management, drawn like the DAMA wheel for data.','I'],
['Unit of work','The smallest task in a capability that one person can pick up and finish.','B'],
['Easy read','A short plain-language summary at the top of each view.','B'],
['Display settings','The Display menu at the top: larger text, easier spacing, reduced motion and high contrast, saved in this browser.','B'],
['Caldicott Guardian','The senior person in health and care responsible for protecting the confidentiality of patient information.','I'],
['CDIO','Chief digital and information officer.','B'],
['DPO','Data protection officer, a statutory role under UK GDPR.','B'],
['DRO','Departmental record officer: leads a department\'s compliance with the Public Records Act.','I'],
['DSPT','Data Security and Protection Toolkit: the annual self-assessment for organisations with access to NHS data and systems.','B'],
['DUAA','Data (Use and Access) Act 2025.','B'],
['Evolution, reform, revolution','Three kinds of change: improve what exists; change the rules and structures; change the system.','B'],
['H1, H2, H3','The Three Horizons: today\'s system, the transition, and the future being sought (GO-Science Futures Toolkit).','B'],
['NDL','National Data Library.','D'],
['PRSA','Public Records (Scotland) Act 2011.','I'],
['RMP','Records management plan agreed with the Keeper of the Records of Scotland.','I'],
['ASSR','Appraisal, selection and sensitivity review: how records are chosen and reviewed before transfer to The National Archives.','I'],
['ATRS','Algorithmic Transparency Recording Standard: published records of algorithmic tools used by the public sector.','A'],
['CDA','Critical data asset: a data asset in scope of the DAM Policy.','D'],
['DAM','Data asset management, as set out in the DAM Policy and the DAM capability playbooks.','D'],
['DCAT','Data Catalog Vocabulary: the W3C standard for describing datasets in catalogues.','D'],
['DD','Deputy Director.','B'],
['EIR','Environmental Information Regulations 2004.','I'],
['FOI','Freedom of Information Act 2000.','I'],
['GDDCF','Government Digital and Data Capability Framework.','D'],
['GKIM','Government Knowledge and Information Management: the profession and the central team.','I'],
['GovS','Government Functional Standards, for example GovS 005 Digital and GovS 007 Security.','B'],
['IAM','Information asset manager: supports an IAO day to day. Also short for information asset management.','I'],
['IAO','Information asset owner: the senior person accountable for an information asset.','I'],
['IAR','Information asset register: the inventory of information assets with owners, risks and retention.','I'],
['IMA','Information Management Assessment by The National Archives.','I'],
['KIM','Knowledge and information management.','I'],
['OAIS','Open Archival Information System reference model (ISO 14721).','I'],
['PRA','Public Records Act 1958.','I'],
['Records of processing','The record of personal data processing that UK GDPR requires.','B'],
['S46 Code','The Lord Chancellor\'s Code of Practice on records management under section 46 of FOIA.','I'],
['SIRO','Senior information risk owner.','I'],
['TNA','The National Archives.','I'],
['xGov MEM','The cross-government Metadata Exchange Model, based on DCAT and endorsed by the Data Standards Authority Steering Board.','D']
];

const SRC=[
['DAM capability playbooks: capability model','https://cyberdudeuk.github.io/dam-capability-playbooks/capability-model.html','v'],
...STD.map(s=>[s.name+': '+s.status,s.url,'v']),
['GO-Science Futures Toolkit (Three Horizons)','https://www.gov.uk/government/publications/futures-toolkit-for-policy-makers-and-analysts/the-futures-toolkit-html','v']
];
const DATA={META,OBJ,DCL,ICL,CAPS,GAPS,JOINS,TL,ROLES,STD,THEMES,XW,GLOSS};

/* ---------- glossary helper ---------- */
const GMAP=Object.fromEntries(GLOSS.map(g=>[g[0],g[1]]));
const gl=s=>esc(s).replace(/\b(IAR|IAO|DAM|DCAT|GKIM|KIM|ATRS|FOI|EIR|TNA|PRA|SIRO|OAIS|GovS|GDDCF|ASSR|IMA|DSPT|DPO|DRO|NDL|PRSA|CDIO|DUAA)\b/g,m=>`<abbr class="g" data-g="${m}" tabindex="0">${m}</abbr>`);
const provTag=p=>p==='v'?'<span class="tag v">Verified</span>':p==='d'?'<span class="tag d">Draft</span>':'<span class="tag p">Proposed</span>';
const relClass=r=>'r-'+r;
const fmtDate=d=>new Date(d+'T12:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});

/* ---------- self checks ---------- */
function selfCheck(D,today){
 const out=[];const add=(id,name,pass,detail,defect,warn)=>out.push({id,name,pass,detail,defect,warn:!!warn});
 const ids=D.CAPS.map(c=>c.id);const want=Array.from({length:32},(_,i)=>'CR-'+String(i+1).padStart(2,'0'));
 add('K1','All 32 DAM capabilities present once',want.every(w=>ids.includes(w))&&new Set(ids).size===ids.length&&ids.length===32,ids.length+' found','A capability could be dropped or duplicated when the list is edited');
 const relOk=D.CAPS.every(c=>['shared','adapt','data'].includes(c.rel)&&(c.rel==='data'?c.ic==='':!!D.ICL[c.ic]));
 add('K2','Every capability has a valid relationship and information cluster',relOk,'','A shared or adapted capability without an information cluster would vanish from the cluster bars');
 const gOk=D.GAPS.every(x=>D.ICL[x.ic]&&x.proc&&x.act&&x.unit&&x.src);
 add('K3','Every gap has a cluster, a full breakdown and a source',gOk,D.GAPS.length+' gaps','A gap without a unit of work breaks the drill-down');
 const stdOk=D.STD.every(s=>/^https:\/\//.test(s.url)&&s.fact&&s.status&&s.dom.length&&D.THEMES.every(t=>t[0] in s.cov));
 add('K8','Every standard has a source, a status and a full theme row',stdOk,D.STD.length+' references','A reference without a source would break the verify-never-fabricate rule');
 const xOk=D.XW.every(r=>['core','extension','IAR-only'].includes(r[4]));
 add('K9','Every IAR crosswalk row has a fit category',xOk,D.XW.length+' fields','A row without a fit category skews the crosswalk counts');
 const stale=today>D.META.nextReview;
 add('K10','Content is within its review date',!stale,'Next review '+D.META.nextReview,'Content may go stale after the next monthly review',stale);
 const text=JSON.stringify(D);
 const forbidden=[/Data Management Team/i,/Office of the Chief Data Officer/i,/\bOCDO\b/,/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}/];
 add('K11','No team names, retired organisation names or email addresses in the content',!forbidden.some(r=>r.test(text)),'','Contact is by form only; the retired organisation name must not appear');
 if(D.LAND){const enumsOk=D.LAND.every(x=>RELS.includes(x.rel)&&['BAU','Change'].includes(x.lens)&&TX.includes(x.tx)&&HZ.includes(x.hz)&&SECTORS.includes(x.sec)&&(/^https:\/\//.test(x.url)||(x.url===''&&x.prov==='d')));
 add('K12','Every landscape item has valid tags and a source or a draft label',enumsOk,D.LAND.length+' developments','An untagged item would vanish from the lens, horizon and relationship views');
 add('K13','AI view covers all eight information clusters',Object.keys(D.ICL).every(k=>D.AIROWS.some(r=>r[0]===k)),'','A cluster without an AI row would hide where AI helps or needs governing');
 add('K14','Every calendar entry has a valid lane and month',D.CAL.every(c=>D.CLANES.includes(c[0])&&Number.isInteger(c[1])&&c[1]>=0&&c[1]<=12&&c[2]&&(c[4]===''||/^https:\/\//.test(c[4]))),D.CAL.length+' entries','A bad month would drop an obligation off the annual cycle');
 add('K15','Every operating model cites at least two sources',D.MODELS.every(m=>m.ev.length>=2&&m.ev.every(e=>/^https:\/\//.test(e[1]))),'','An unsourced example would break verify-never-fabricate');
 add('K16','Every skills framework has a source',D.SKILLS.every(x=>/^https:\/\//.test(x[3])),D.SKILLS.length+' frameworks','A framework without a source cannot be checked');
 add('K18','Every further gap points to a view that exists',D.MOREGAPS.every(g=>/^GX-\d+$/.test(g[0])&&GXMAP[g[2]]&&VIEWS.some(v=>v[0]===GXMAP[g[2]])),D.MOREGAPS.length+' gaps','A gap linking to a missing view is a dead end');}
 if(D.PERSONAS){const pw=new Set(D.PATHS.map(x=>x.id));
 add('K19','Every persona has a five-stage journey, a pathway and a valid role',D.PERSONAS.every(p=>{const J=D.JOURNEYS[p.journey];return J&&J.length===STAGES.length&&J.every((s,i)=>s[0]===STAGES[i])&&pw.has(p.path)&&(p.role===null||!!D.ROLES[p.role])}),D.PERSONAS.length+' personas','D6: a persona pointing at a missing journey or pathway would offer a route that goes nowhere');
 const stepOk=(v,sec,l,t)=>VIEWS.some(x=>x[0]===v)&&(!sec||(D.SECTIONS&&(D.SECTIONS[v]||[]).includes(sec)))&&['','BAU','Change'].includes(l)&&['',...TX].includes(t);
 const steps=[...Object.values(D.JOURNEYS).flat().map(s=>[s[2],s[3],s[4],s[5]]),...D.PATHS.flatMap(P=>P.steps.map(s=>[s[0],s[1],s[2],s[3]]))];
 add('K20','Every journey and pathway step opens a real view and section with a valid lens',!!D.SECTIONS&&steps.every(s=>stepOk(...s)),steps.length+' steps','D6: a step naming a renamed section or an unknown lens value would open the wrong place silently');
 const combos=D.WTEAMS.flatMap(t=>D.WLEVELS.flatMap(l=>D.WAYGOALS.map(g=>wayfind(t[0],l[0],g[0],D))));
 const reach=new Set(combos.map(c=>c.path));
 add('K21','The wayfinder answers every combination and reaches every pathway',combos.every(c=>D.PERSONAS.some(p=>p.id===c.persona)&&pw.has(c.path))&&D.PATHS.every(P=>reach.has(P.id)),combos.length+' combinations','D6: an unanswered combination leaves a reader with no route; an unreachable pathway is never suggested');
 const lm=D.LENSMAP;
 add('K22','Every view declares what the lenses do, and each claim matches the data tags',VIEWS.every(v=>{const m=lm[v[0]];if(!m)return false;if(!m.lens)return !m.tx&&!!m.note;const items=D[m.src];return Array.isArray(items)&&items.length>0&&items.every(x=>['BAU','Change'].includes(x[m.lf]))&&(!m.tx||items.every(x=>TX.includes(x[m.tf])))}),Object.keys(lm).length+' views declared','D5: the lens bar showed on every view but filtered only some, and transformation only two, with no explanation');
 add('K23','New wayfinding terms are in the glossary',['Lens','Change','Persona','Journey','Pathway','Wayfinder'].every(t=>D.GLOSS.some(g=>g[0]===t)),'','A new concept without a definition breaks the tooltip and glossary promise');}
 if(D.WHEEL){const known=new Set([...D.CAPS.map(c=>c.id),...D.GAPS.map(g=>g.id)]),stdOk=s=>!s||s.split(',').every(x=>D.STD.some(y=>y.id===x));
 const wids=D.WHEEL.flatMap(w=>w.caps.map(c=>typeof c==='string'?c:c[0]));
 add('K25','The information wheel is complete: a hub and 12 areas, each capability drills down to a unit of work, every link resolves, every gap has a place',D.WHEEL.length===13&&D.WHEEL.every(w=>WFAM[w.fam]&&w.caps.length&&w.short&&w.what&&stdOk(w.std)&&w.caps.every(c=>typeof c==='string'?D.GAPS.some(g=>g.id===c):c.length===7&&c[1]&&c[2]&&c[3]&&c[4]&&(!c[5]||c[5].split(',').every(r=>known.has(r)))&&stdOk(c[6])))&&new Set(wids).size===wids.length&&D.GAPS.every(g=>wids.includes(g.id)),wids.length+' capabilities','Rule (2.2.0): a capability without a unit of work, or a link to a missing item, would strand a reader part-way down the wheel');
 add('K26','Every view has a short easy-read summary, and the user guide is complete',VIEWS.every(v=>D.EASY[v[0]]&&D.EASY[v[0]].length<=200)&&D.GUIDE.length>=8&&D.GUIDE.every(g=>g[0]&&g[1]),Object.keys(D.EASY).length+' summaries','Rule (2.2.0): a view without a plain-language summary leaves readers new to the topic without a way in');}


 if(D.H2ICON){add('K27','Every section heading has a fitting icon, and every display setting is defined',typeof document==='undefined'||[...document.querySelectorAll('h2[id]')].filter(h=>!/^sh-/.test(h.id)).every(h=>h2icon(h.id)&&ICO[h2icon(h.id)]),D.DISP.length+' display settings','Rule (2.3.0): a heading without an icon breaks the visual pattern readers learn to scan by');}
 add('K24','The public edition carries no internal working material',!/(KIM Baseline|away day|check-in|working draft|Government Information Accountability|meeting notes|Purview pilot|DM Hub|17 November|17 December|Risk Baseline|Discoverability Platform)/i.test(JSON.stringify(D))&&!(D.LAND||[]).some(x=>x.prov==='d')&&!D.JOINS.length&&!D.TL.length&&!Object.keys(D.ROLES).length,'','D9: the internal edition holds draft and meeting-derived material that must not reach the public site');
 return out;
}

/* ---------- views ---------- */
const VIEWS=[['overview','Overview','M3 10l7-6 7 6v7H3z'],['start','Find your way','M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM13 7l-2 4-4 2 2-4z'],['landscape','Landscape','M2 15l5-6 4 4 3-3 4 5z'],['capabilities','Capabilities','M3 4h14v3H3zM3 9h14v3H3zM3 14h14v3H3z'],['gaps','Gaps','M4 4h5v5H4zM11 11h5v5h-5z'],['wheel','Information wheel','M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM10 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM10 2v4M10 14v4M2 10h4M14 10h4'],['standards','Standards','M4 3h9l3 3v11H4z'],['ai','AI','M10 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z'],['skills','Skills','M3 8l7-4 7 4-7 4zM6 10v4c2 2 6 2 8 0v-4'],['models','Operating models','M4 4h4v4H4zM12 4h4v4h-4zM8 14h4v4H8zM6 8v3h8V8M10 11v3'],['calendar','Calendar','M3 5h14v12H3zM3 9h14M7 3v4M13 3v4'],['horizons','Horizons','M2 16c4-8 12-8 16 0M2 16c3-5 7-6 10-4'],['glossary','Glossary','M5 3h10v14H5zM8 7h4'],['about','About and checks','M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM10 9v4M10 6v1']];
const nav=document.getElementById('navlist');
nav.innerHTML=VIEWS.map(v=>`<li data-v="${v[0]}"><a href="#${v[0]}"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="${v[2]}" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>${esc(v[1])}</a></li>`).join('');

function fitNav(){const more=document.getElementById('more'),ml=document.getElementById('morelist');
 [...ml.children].forEach(li=>nav.appendChild(li));more.hidden=true;
 const order=VIEWS.map(v=>v[0]);[...nav.children].sort((a,b)=>order.indexOf(a.dataset.v)-order.indexOf(b.dataset.v)).forEach(li=>nav.appendChild(li));
 const total=[...nav.children].reduce((a,li)=>a+li.offsetWidth+2,0);const full=nav.parentElement.clientWidth-32;
 if(total<=full)return;const avail=full-110;let used=0;[...nav.children].forEach(li=>{used+=li.offsetWidth+2;if(used>avail)ml.appendChild(li)});more.hidden=!ml.children.length;}

/* overview */
function figs(){const sh=CAPS.filter(c=>c.rel==='shared').length,ad=CAPS.filter(c=>c.rel==='adapt').length,da=CAPS.filter(c=>c.rel==='data').length;
 const F=[[CAPS.length,'DAM capabilities'],[sh,'shared by both worlds'],[ad,'need an information version'],[da,'data only'],[GAPS.length,'information-only gaps',1],[STD.length,'standards and models compared'],[LAND.length,'developments in the landscape scan',1]];
 document.getElementById('figs').innerHTML=F.map(f=>`<div class="fig1${f[2]?' hot':''}"><b data-n="${f[0]}">0</b><span>${esc(f[1])}</span></div>`).join('');
 const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches||document.documentElement.classList.contains('d-rm');
 document.querySelectorAll('#figs b').forEach(b=>{const n=+b.dataset.n;if(reduce){b.textContent=n;return}let i=0;const t=setInterval(()=>{i++;b.textContent=Math.round(n*i/20);if(i>=20)clearInterval(t)},30)});}
function board(){const L=[['data','Data only','Stays in the DAM playbooks.'],['shared','Shared by both worlds','One approach serves data and information.'],['adapt','Needs an information version','Same capability, different rules and sources.'],['gap','Gap: information only','Not covered by the DAM playbooks today.']];
 const items=r=>r==='gap'?GAPS:CAPS.filter(c=>c.rel===r);
 document.getElementById('board').innerHTML=L.map(l=>`<div class="lane"><h3>${esc(l[1])}<span class="cnt">${items(l[0]).length}</span></h3><p>${esc(l[2])}</p><div class="chips">${items(l[0]).map(c=>`<button class="chip ${relClass(c.rel)}" data-open="${c.id}" type="button"><b>${c.id}</b>${esc(c.name)}</button>`).join('')}</div></div>`).join('');}
function cbars(){const max=Math.max(...Object.keys(ICL).map(k=>CAPS.filter(c=>c.ic===k).length+GAPS.filter(x=>x.ic===k).length));
 document.getElementById('cbars').innerHTML=Object.entries(ICL).map(([k,n])=>{const s=CAPS.filter(c=>c.ic===k&&c.rel==='shared').length,a=CAPS.filter(c=>c.ic===k&&c.rel==='adapt').length,gp=GAPS.filter(x=>x.ic===k).length;
 return `<div class="brow"><span>${esc(n)}</span><div class="btrack" role="img" aria-label="${esc(n)}: ${s} shared, ${a} need an information version, ${gp} gaps"><span class="b-shared" style="width:${s/max*100}%"></span><span class="b-adapt" style="width:${a/max*100}%"></span><span class="b-gap" style="width:${gp/max*100}%"></span></div><span style="white-space:nowrap;font-size:13px">${s} · ${a} · <strong style="color:var(--info)">${gp}</strong></span></div>`}).join('')+`<p style="font-size:13px;color:var(--mute);margin:6px 0 0">Shared · needs an information version · <strong style="color:var(--info)">gap</strong></p>`;}
const TODAY=new Date().toISOString().slice(0,10);

/* capabilities */
function capFilters(){document.getElementById('f-dc').innerHTML+=Object.entries(DCL).map(([k,v])=>`<option value="${k}">${esc(v)}</option>`).join('');}
function capTable(){const r=document.getElementById('f-rel').value,dc=document.getElementById('f-dc').value,ob='',q=document.getElementById('f-q').value.trim().toLowerCase();
 const rows=CAPS.filter(c=>(!r||c.rel===r)&&(!dc||c.dc===dc)&&(!ob||c.obj.includes(ob))&&(!q||(c.id+' '+c.name+' '+c.info+' '+c.gkim).toLowerCase().includes(q)));
 document.getElementById('c-count').textContent=rows.length+' of '+CAPS.length+' capabilities shown';
 document.querySelector('#ctable tbody').innerHTML=rows.length?rows.map(c=>`<tr data-open="${c.id}" tabindex="0"><td><strong>${c.id}</strong></td><td>${esc(c.name)}</td><td>${esc(DCL[c.dc])}</td><td>${FLAG[c.flag]}</td><td><span class="chip ${relClass(c.rel)}" style="cursor:default;min-height:0;padding:2px 6px">${REL[c.rel]}</span></td><td>${gl(c.info)}</td></tr>`).join(''):'<tr><td colspan="6">No capabilities match. Reset the filters.</td></tr>';}

/* gaps */
function gaps(){document.getElementById('gaplist').innerHTML=Object.entries(ICL).map(([k,n])=>{const gs=GAPS.filter(x=>x.ic===k);const cov=CAPS.filter(c=>c.ic===k);
 return `<h2 id="g-${k}">${esc(n)} <span class="cnt">${gs.length} gap${gs.length===1?'':'s'}</span></h2>${cov.length?`<p style="font-size:14px;color:var(--mute)">Already covered through DAM: ${cov.map(c=>`<button class="chip ${relClass(c.rel)}" data-open="${c.id}" type="button" style="min-height:30px;padding:2px 6px"><b>${c.id}</b></button>`).join(' ')}</p>`:''}${gs.length?gs.map(x=>`<details class="card"><summary><strong>${x.id}</strong> ${esc(x.name)} <span class="tag p">Proposed</span></summary><div class="in"><div class="flow" aria-label="Breakdown from domain to unit of work">${[['Domain','Information asset management'],['Cluster',n],['Capability',x.name],['Process',x.proc],['Activity',x.act],['Unit of work',x.unit]].map((s,i,a)=>`<div class="step${i===a.length-1?' last':''}"><small>${s[0]}</small>${esc(s[1])}</div>${i<a.length-1?'<span class="arrow" aria-hidden="true">→</span>':''}`).join('')}</div><dl class="kv"><dt>Grounded in</dt><dd>${gl(x.src)}</dd></dl></div></details>`).join(''):'<p>No information-only gaps in this cluster.</p>'}`}).join('');}

/* standards */
function stdCards(){const sel=document.getElementById('f-typ');if(sel.options.length<2)sel.innerHTML+=[...new Set(STD.map(s=>s.type))].map(t=>`<option>${esc(t)}</option>`).join('');
 const d=document.getElementById('f-dom').value,t=sel.value;const DN={D:'Data',I:'Information',K:'Knowledge',A:'AI'};
 document.getElementById('stdcards').innerHTML=STD.filter(s=>(!d||s.dom.includes(d))&&(!t||s.type===t)).map(s=>`<article class="jcard"><div>${s.dom.map(x=>`<span class="dom ${x}">${DN[x]}</span>`).join('')}<span class="tag">${esc(s.type)}</span></div><h3>${esc(s.name)}</h3><p style="margin:0">${gl(s.what)}</p><p style="margin:0;font-size:14px"><span class="tag v">Verified</span> ${gl(s.fact)}</p><p style="margin:0;font-size:13px;color:var(--mute)">${esc(s.status)} · <a href="${esc(s.url)}">Source</a></p></article>`).join('');}
function matrix(){const DN={D:'D',I:'I',K:'K',A:'A'};
 document.getElementById('mx').innerHTML=`<thead><tr><th>Theme</th>${STD.map(s=>`<th title="${esc(s.name)}">${esc(s.id)}</th>`).join('')}<th>Core in</th></tr></thead><tbody>${THEMES.map(t=>{const core=STD.filter(s=>s.cov[t[0]]===2);const doms=[...new Set(core.flatMap(s=>s.dom))];return `<tr><td>${esc(t[1])}</td>${STD.map(s=>`<td>${s.cov[t[0]]===2?'<span class="dotc" aria-label="core"></span>':s.cov[t[0]]===1?'<span class="dotc h" aria-label="touches"></span>':''}</td>`).join('')}<td>${doms.map(x=>`<span class="dom ${x}">${DN[x]}</span>`).join('')}</td></tr>`}).join('')}</tbody>`;
 const shared=THEMES.filter(t=>{const doms=new Set(STD.filter(s=>s.cov[t[0]]===2).flatMap(s=>s.dom));return doms.size>=2});
 document.getElementById('sharedtxt').innerHTML=`<p>${shared.length} of ${THEMES.length} themes are a core concern in more than one world: ${shared.map(t=>esc(t[1].toLowerCase())).join('; ')}. These are where one capability, one register entry and one owner can serve data, information and AI together.</p>`;
 document.getElementById('uniq').innerHTML=UNIQ.map(u=>`<div class="jcard"><div><span class="dom ${u[0]}">${u[1].replace('Unique to ','')}</span></div><h3>${esc(u[1])}</h3><p style="margin:0">${gl(u[2])}</p></div>`).join('');}
function xwalk(){const c=k=>XW.filter(r=>r[4]===k).length;
 document.getElementById('xfigs').innerHTML=[[XW.length,'common IAR fields mapped'],[c('core'),'map to a DCAT core term'],[c('extension'),'need a UK extension',1],[c('IAR-only'),'stay IAR-only']].map(f=>`<div class="fig1${f[2]?' hot':''}"><b>${f[0]}</b><span>${esc(f[1])}</span></div>`).join('');
 document.querySelector('#xwalk tbody').innerHTML=XW.map(r=>`<tr><td><strong>${gl(r[0])}</strong></td><td><code>${esc(r[1])}</code></td><td>${esc(r[2])}</td><td>${gl(r[3])}</td><td><span class="tag ${r[4]==='core'?'v':r[4]==='extension'?'p':'d'}">${r[4]==='core'?'Core':r[4]==='extension'?'Extension':'IAR-only'}</span></td></tr>`).join('');}



/* glossary */
function glossary(){const q=(document.getElementById('g-q').value||'').toLowerCase();const W={D:'Data',I:'Information',A:'AI',B:'Both'};
 document.querySelector('#gtable tbody').innerHTML=GLOSS.filter(x=>!q||(x[0]+' '+x[1]).toLowerCase().includes(q)).map(x=>`<tr><td><strong>${esc(x[0])}</strong></td><td>${esc(x[1])}</td><td>${W[x[2]]}</td></tr>`).join('');}

/* about */
function about(){const seen=new Set(SRC.map(x=>x[1]));[...LAND.filter(x=>x.url).map(x=>[x.t+' ('+x.who+')',x.url,'v']),...SKILLS.map(x=>[x[0],x[3],'v']),...MODELS.flatMap(m=>m.ev.map(e=>[e[0],e[1],'v']))].forEach(x=>{if(!seen.has(x[1])){seen.add(x[1]);SRC.push(x)}});document.getElementById('srcs').innerHTML='<ul>'+SRC.map(s=>`<li>${s[1]?`<a href="${esc(s[1])}">${esc(s[0])}</a>`:esc(s[0])+' (internal working file)'} ${provTag(s[2])}</li>`).join('')+'</ul>';
 document.getElementById('nextrev').textContent=fmtDate(META.nextReview);document.getElementById('ver').textContent=META.version;
 const res=selfCheck(DATA,TODAY);const fails=res.filter(r=>!r.pass&&!r.warn).length,warns=res.filter(r=>r.warn).length;
 document.getElementById('checks').innerHTML=res.map(r=>`<li><span class="${r.pass?'ok':r.warn?'wn':'no'}">${r.pass?'Pass':r.warn?'Warn':'Fail'}</span><span><strong>${r.id}</strong> ${esc(r.name)}${r.detail?' · '+esc(r.detail):''}<br><small style="color:var(--mute)">Guards against: ${esc(r.defect)}</small></span></li>`).join('');
 document.getElementById('stattext').textContent=fails?fails+' check'+(fails>1?'s':'')+' failing':warns?'Review due':'All '+res.length+' checks pass';
 document.getElementById('pulse').classList.toggle('bad',!!fails);
 if(TODAY>META.nextReview)document.getElementById('revline').textContent='Review overdue: last reviewed 16 November 2026';}

/* detail sheet */
const sheet=document.getElementById('sheet'),scrim=document.getElementById('scrim');let lastFocus=null;
function openDetail(id){const c=CAPS.find(x=>x.id===id),x=GAPS.find(y=>y.id===id);let h;
 if(c){
  h=`<p class="lbl">${esc(DCL[c.dc])}</p><h2 id="sh-title" style="margin-top:0">${c.id} ${esc(c.name)}</h2><p><span class="chip ${relClass(c.rel)}" style="cursor:default">${REL[c.rel]}</span></p><dl class="kv"><dt>In the DAM Policy</dt><dd>${FLAG[c.flag]}</dd><dt>Information-world counterpart</dt><dd>${gl(c.info)}</dd><dt>Information cluster</dt><dd>${c.ic?esc(ICL[c.ic]):'Not applicable'}</dd></dl><p><a href="https://cyberdudeuk.github.io/dam-capability-playbooks/capability-model.html">Open the DAM capability model</a></p><p class="note">The relationship and cluster are this resource's proposals.</p>`;}
 else if(x){h=`<p class="lbl">${esc(ICL[x.ic])}</p><h2 id="sh-title" style="margin-top:0">${x.id} ${esc(x.name)}</h2><p><span class="chip r-gap" style="cursor:default">${REL.gap}</span></p><dl class="kv"><dt>Process</dt><dd>${esc(x.proc)}</dd><dt>Activity</dt><dd>${esc(x.act)}</dd><dt>Unit of work</dt><dd>${esc(x.unit)}</dd><dt>Grounded in</dt><dd>${gl(x.src)}</dd></dl><p><a href="#gaps">See all gaps</a></p>`;}
 else return;
 document.getElementById('shbody').innerHTML=h;lastFocus=document.activeElement;sheet.classList.add('open');scrim.classList.add('open');sheet.focus();}
function closeDetail(){sheet.classList.remove('open');scrim.classList.remove('open');if(lastFocus)lastFocus.focus();}
document.getElementById('shclose').addEventListener('click',closeDetail);scrim.addEventListener('click',closeDetail);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&sheet.classList.contains('open'))closeDetail();if((e.key==='Enter'||e.key===' ')&&e.target.matches('tr[data-open]')){e.preventDefault();openDetail(e.target.dataset.open)}});
document.addEventListener('click',e=>{const o=e.target.closest('[data-open]');if(o){openDetail(o.dataset.open);return}
 const j=e.target.closest('[data-jump]');if(j){closeDetail();setTimeout(()=>{const el=document.getElementById(j.dataset.jump);if(el)el.scrollIntoView({behavior:SMOOTH()})},250)}
 const t=e.target.closest('[data-tl]');if(t){const ev=TL[+t.dataset.tl];document.getElementById('shbody').innerHTML=`<p class="lbl">${ev.lane}</p><h2 id="sh-title" style="margin-top:0">${fmtDate(ev.d)}</h2><p>${gl(ev.t)}</p><p>${provTag(ev.prov)}</p>`;lastFocus=t;sheet.classList.add('open');scrim.classList.add('open');sheet.focus()}});

/* tabs */
function wireTabs(listId){const list=document.getElementById(listId);list.addEventListener('click',e=>{const b=e.target.closest('[role=tab]');if(!b)return;list.querySelectorAll('[role=tab]').forEach(t=>{const on=t===b;t.setAttribute('aria-selected',on);document.getElementById(t.getAttribute('aria-controls')).hidden=!on});buildToc()});
 list.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;const tabs=[...list.querySelectorAll('[role=tab]')];const i=tabs.indexOf(document.activeElement);const n=tabs[(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length];n.focus();n.click()});}

/* tooltip */
const tip=document.getElementById('tip');
function showTip(el){const d=GMAP[el.dataset.g];if(!d)return;tip.textContent=el.dataset.g+': '+d;tip.style.display='block';const r=el.getBoundingClientRect();tip.style.left=Math.min(r.left,innerWidth-310)+'px';tip.style.top=(r.bottom+6)+'px';}
document.addEventListener('mouseover',e=>{const a=e.target.closest('abbr.g');if(a)showTip(a)});document.addEventListener('focusin',e=>{const a=e.target.closest('abbr.g');if(a)showTip(a)});
document.addEventListener('mouseout',e=>{if(e.target.closest('abbr.g'))tip.style.display='none'});document.addEventListener('focusout',e=>{if(e.target.closest('abbr.g'))tip.style.display='none'});

/* drawer */
const shell=document.getElementById('shell'),dtog=document.getElementById('dtog');
function setDrawer(open){shell.classList.toggle('closed',!open);dtog.setAttribute('aria-expanded',open);try{localStorage.setItem('age-drawer',open?'1':'0')}catch(e){}}
dtog.addEventListener('click',()=>setDrawer(dtog.getAttribute('aria-expanded')!=='true'));
function buildToc(){if(typeof decorate==='function')decorate();const v=document.querySelector('.view:not([hidden])');if(!v)return;const hs=[...v.querySelectorAll('h2[id]')].filter(h=>!h.closest('[hidden]'));
 const counts={'o-board':CAPS.length+GAPS.length,'c-list':CAPS.length,'s-models':STD.length,'s-xwalk':XW.length,'j-others':OTHERS.length,'t-list':TL.length,'a-checks':(window.__NCHK||0),'l-items':LAND.length,'ai-table':8,'k-frameworks':SKILLS.length,'k-roles':ROLEX.length,'cal-dated':CALDATED.length,'own-check':OWNCHK.length,'g-more':MOREGAPS.length};
 document.getElementById('toc').innerHTML=hs.map(h=>{const id=h.id;const cnt=counts[id]??(id.startsWith('g-')?GAPS.filter(x=>'g-'+x.ic===id).length:null);return `<li><a href="#${v.dataset.view}" data-to="${id}"><span>${ico(h2icon(id)||'list','ti')}${esc(textOf(h))}${['w-find','w-personas','w-journeys','w-paths','w-map','w-lenses','o-start'].includes(id)?'<span class="new">New</span>':''}</span>${cnt!=null?`<span class="cnt">${cnt}</span>`:''}</a></li>`}).join('')||'<li>No sections</li>';}
document.getElementById('toc').addEventListener('click',e=>{const a=e.target.closest('[data-to]');if(!a)return;e.preventDefault();document.getElementById(a.dataset.to).scrollIntoView({behavior:SMOOTH()});if(innerWidth<=900)setDrawer(false)});

/* router */
function route(){const H=parseHash();let v=H.v;if(!VIEWS.some(x=>x[0]===v))v='overview';const p=H.p;
 if(p.has('lens')||p.has('tx')){const l=p.get('lens')||'',t=p.get('tx')||'';LENS.lens=['','BAU','Change'].includes(l)?l:'';LENS.tx=['',...TX].includes(t)?t:'';renderLensViews();}
 if(p.has('pw')&&PATHS.some(x=>x.id===p.get('pw')))PATH={id:p.get('pw'),s:Math.max(0,parseInt(p.get('s'),10)||0)};
 if(v==='start'&&p.get('tab'))selectTab('wtabs','wt-'+p.get('tab'));
 if(v==='wheel'&&typeof wheelParams==='function')wheelParams(p);
 document.querySelectorAll('.view').forEach(s=>s.hidden=s.dataset.view!==v);
 document.querySelectorAll('nav.global a').forEach(a=>a.getAttribute('href')==='#'+v?a.setAttribute('aria-current','page'):a.removeAttribute('aria-current'));
 buildToc();lensBar();trail();if(typeof mastH==='function')mastH();const to=p.get('to'),el=to&&document.getElementById(to);if(el&&!el.closest('[hidden]')){el.scrollIntoView();}else window.scrollTo(0,0);}
addEventListener('hashchange',route);

/* more menu */
const mb=document.getElementById('morebtn');mb.addEventListener('click',()=>{const m=document.getElementById('more');const o=!m.classList.contains('open');m.classList.toggle('open',o);mb.setAttribute('aria-expanded',o)});
document.getElementById('morelist').addEventListener('click',()=>{document.getElementById('more').classList.remove('open');mb.setAttribute('aria-expanded','false')});

/* filters */
['f-rel','f-dc'].forEach(id=>document.getElementById(id).addEventListener('change',capTable));document.getElementById('f-q').addEventListener('input',capTable);
document.getElementById('f-reset').addEventListener('click',()=>{['f-rel','f-dc','f-q'].forEach(id=>document.getElementById(id).value='');capTable()});
['f-dom','f-typ'].forEach(id=>document.getElementById(id).addEventListener('change',stdCards));
document.getElementById('g-q').addEventListener('input',glossary);

const GXMAP={'Skills':'skills','Calendar':'calendar','AI':'ai','Landscape':'landscape','Operating models':'models'};

/* ===== Release 2.0: landscape, AI, skills, operating models, calendar, horizons, own assets ===== */
const RELS=['converge','align','integrate','consolidate','combine','merge','diverge'];
const RELTXT={converge:'Converge: moving towards the same assets, owners or methods',align:'Align: separate but deliberately consistent',integrate:'Integrate: built into another regime',consolidate:'Consolidate: several things brought into one',combine:'Combine: run together by one team',merge:'Merge: two roles or regimes become one',diverge:'Diverge: deliberately separate or moving apart'};
const SECTORS=['Central government','Health and care','Devolved','Local government','Policing','Cross-cutting','International'];
const TX=['Evolution','Reform','Revolution'];const HZ=['H1','H2','H3'];
const HZTXT={H1:'Horizon 1: keep today\'s system running well',H2:'Horizon 2: the transition, innovations that bridge',H3:'Horizon 3: the future system being sought'};
// id, title, who, when, sector, domains, what, relationship, lens, transformation, horizon, url, provenance
const LAND=[
['L01','DAM Policy published','GDS','2026','Central government','D','Departments and arm\'s length bodies must identify, record and report their most important data assets.','converge','Change','Reform','H2','https://www.thinkdigitalpartners.com/news/2026/06/04/government-orders-departments-to-treat-data-as-a-strategic-asset','v'],
['L03','Roadmap for modern digital government','GDS','Jan 2026','Central government','DAL','Action plan to 2030, including a strategic roadmap for public sector data, core data standards and an API mandate.','consolidate','Change','Reform','H2','https://roadmap-for-modern-digital-government.campaign.gov.uk/digital-and-data-infrastructure/frameworks-for-data-use','v'],
['L04','Strategic Data Roadmap','Government Chief Data Officer','Autumn 2026','Central government','D','Long-term plan for how public data is governed, accessed and used.','integrate','Change','Reform','H2','https://dataingovernment.blog.gov.uk/2026/09/03/connecting-data-to-enable-modern-digital-government/','v'],
['L05','National Data Library launched','DSIT and GDS','June 2026','Central government','DA','data.gov.uk is being turned into a single gateway to curated, high-quality public sector data.','consolidate','Change','Revolution','H3','https://www.data.gov.uk/about/','v'],
['L06','Guidelines for AI-ready datasets','GDS','Jan 2026','Central government','DA','Four pillars for AI-ready datasets, including data and metadata quality.','converge','Change','Reform','H2','https://www.gov.uk/government/publications/making-government-datasets-ready-for-ai/guidelines-and-best-practices-for-making-government-datasets-ready-for-ai','v'],
['L07','Data and AI Ethics Framework refreshed','GDS','Jan 2026','Central government','DA','One framework for the ethics of data and AI use in government.','merge','BAU','Evolution','H1','https://roadmap-for-modern-digital-government.campaign.gov.uk/digital-and-data-infrastructure/frameworks-for-data-use','v'],
['L08','Person Data Standard (alpha)','GDS','2026','Central government','D','A common standard for identifying and supporting people at risk across services.','align','Change','Reform','H2','https://dataingovernment.blog.gov.uk/2026/09/03/connecting-data-to-enable-modern-digital-government/','v'],
['L09','Data (Use and Access) Act 2025 in force','DSIT','2025 to 2026','Cross-cutting','DS','Most data protection changes now in force; a complaints requirement commenced in June 2026; reforms diverge from the EU regime.','diverge','BAU','Reform','H1','https://www.kennedyslaw.com/en/thought-leadership/article/2026/the-data-use-and-access-act-2025-commencement-dates-and-planned-guidance-for-2026','v'],
['L10','ATRS mandatory and the AI Playbook','GDS','2024 to 2025','Central government','A','Mandatory records of algorithmic tools for departments and in-scope bodies, alongside the AI Playbook.','align','BAU','Evolution','H1','https://www.gov.uk/government/publications/algorithmic-transparency-recording-standard-mandatory-scope-and-exemptions-policy','v'],
['L11','AI for GKIM community','GKIM','Monthly','Central government','IA','KIM professionals using AI to manage the digital heap and supporting departments to account for their AI use.','converge','Change','Reform','H2','https://www.gov.uk/service-manual/communities/ai-for-government-knowledge-information-management-community','v'],
['L12','TNA Information Management Assessment toolkit','The National Archives','Ongoing','Central government','I','Section 46 maturity tool, Digital ASSR tool developed with the GKIM community, and an M365 tool.','align','BAU','Evolution','H1','https://www.nationalarchives.gov.uk/information-management/manage-information/ima/','v'],
['L13','20-year rule in steady state','The National Archives','Since 2023','Central government','I','Public bodies transfer one year\'s worth of records each year as they turn 20.','diverge','BAU','Evolution','H1','https://www.nationalarchives.gov.uk/about/our-role/transparency/information-management-report/','v'],
['L14','AI steering group at The National Archives','The National Archives','2025 to 2026','Central government','IA','A steering group exploring how emerging technologies could support archival work.','converge','Change','Reform','H2','https://www.nationalarchives.gov.uk/about-us/how-we-work/plans-policies-performance-and-projects/annual-report-and-accounts-2025-26/','v'],
['L15','DSPT 2025 to 2026 (version 8)','NHS England','Dec 2025 and Jun 2026','Health and care','SI','Baseline submission by 31 December 2025, final submission by 30 June 2026.','integrate','BAU','Evolution','H1','https://grcsolutions.io/the-nhs-dspt-data-security-and-protection-toolkit-what-you-need-to-know-for-2025-26/','v'],
['L16','SIRO, Caldicott Guardian and DPO kept distinct','UK Caldicott Guardian Council','Ongoing','Health and care','SI','Distinct but complementary roles, with overlap with the data protection officer.','diverge','BAU','Evolution','H1','https://ukcgc.uk/key-relationships','v'],
['L17','Records management plans and progress reviews','National Records of Scotland','Ongoing','Devolved','I','Authorities agree a records management plan with the Keeper; progress update reviews are voluntary.','diverge','BAU','Evolution','H1','https://nrscotland.gov.uk/publications/guidance-for-completion-of-the-progress-update-review-pur','v'],
['L18','Council information governance teams','Local authorities','Ongoing','Local government','ISD','One team covering data protection, FOI, records and information management.','combine','BAU','Evolution','H1','https://www.doncaster.gov.uk/services/the-council-democracy/information-governance','v'],
['L19','Council data governance offices','Local authorities','2021 onwards','Local government','D','Separate data governance teams owning data architecture, quality and catalogues.','diverge','Change','Reform','H2','https://www.local.gov.uk/node/8281619','v'],
['L20','Policing Information Management Standard','Police Digital Service','Live Jan 2026','Policing','IS','Information management requirements set within the national community security policy.','integrate','BAU','Evolution','H1','https://knowledgehub.group/web/national-standards/live-standards/-/ddl_display/ddl/404328557/362284494/maximized','v'],
['L21','DWP Information Management Policy','DWP','Feb 2026','Central government','IS','Information lifecycle policy within a security policy suite; an IAO assigned to every asset.','integrate','BAU','Evolution','H1','https://gov.uk/government/publications/dwp-information-management-policies/dwp-information-management-policy','v'],
['L22','DWP data strategy to 2030','DWP','Feb 2026','Central government','D','A long-term plan for how the department manages and uses data.','align','Change','Reform','H2','https://www.thinkdigitalpartners.com/news/2026/02/03/dwp-unveils-data-strategy-to-2030-aiming-to-modernise-welfare-services','v'],
['L23','Digital and Data continuous improvement assessment','GDS','Apr 2026','Central government','D','The GovS 005 assessment includes a data theme on roles and governance.','integrate','BAU','Evolution','H1','https://assets.publishing.service.gov.uk/media/69e6593dde262afd82fcf99d/2024-05-13_Digital_CIAF_V1.2.pdf','v'],
['L24','Good practice guide for organisations using AI','NAO','May 2026','Cross-cutting','A','Audit guidance on using AI in public bodies.','align','BAU','Evolution','H1','https://www.nao.org.uk/knowledge','v'],
['L25','Core digital, data, innovation and AI curriculum','Government Digital and Data profession','Apr 2026','Central government','L','A curriculum for all civil servants, building on the 2025 One Big Thing AI programme.','consolidate','Change','Reform','H2','https://analysisfunction.civilservice.gov.uk/ai-hub/ai-learning-and-development/','v'],
['L26','Digital, data and cyber to 10% of the Civil Service','DSIT','By 2030','Central government','L','Growth from about 5% today, with AI and data scientist accelerator cohorts through 2026 to 2027.','consolidate','Change','Revolution','H3','https://committees.parliament.uk/publications/54764/documents/304166/default/','v'],
['L27','Chief data officers expected to carry out records management','US National Archives','2022','International','DI','US guidance expects agency chief data officers to carry out records management.','merge','Change','Revolution','H3','https://www.Archives.gov/files/records-mgmt/resources/cdo-rm-assessment-report.pdf','v'],
['L28','AI is everywhere except records work','National Archives of Australia','Jun 2026','International','IA','87% of agencies use AI, 15% apply it to information management and 8% to create metadata.','converge','Change','Reform','H2','https://idm.net.au/node/15699','v'],
['L29','One chief data and AI officer','US Department of State','2025','International','DA','One officer performs both the chief data officer and chief AI officer roles.','merge','Change','Revolution','H3','https://fam.state.gov/FAM/20FAM/20FAM010201.html','v'],
['L30','Data governance manager role refreshed','Government Digital and Data profession','Aug 2025','Central government','DL','The role defines, implements and manages data governance and encourages data literacy.','align','BAU','Evolution','H1','https://ddat-capability-framework.service.gov.uk/role/data-governance-manager','v'],
['L31','Council policy on AI and algorithmic processing','Local authorities','2024 to 2025','Local government','AI','Information governance boards approving AI automation policies alongside records and data sharing.','integrate','Change','Reform','H2','https://moderngov.dorsetcouncil.gov.uk/documents/s47447/Annual Information Governance Report 202425.pdf','v'],
].map(a=>({id:a[0],t:a[1],who:a[2],when:a[3],sec:a[4],dom:a[5].split(''),what:a[6],rel:a[7],lens:a[8],tx:a[9],hz:a[10],url:a[11],prov:a[12]}));

// AI by information cluster: cluster, AI helps, governance it must apply, what AI governance needs from it, lens
const AIROWS=[
['C1','Summarise returns and assurance evidence; spot patterns across baselines','AI Playbook principles; Data and AI Ethics Framework','Named senior accountability for every asset an AI system uses','BAU'],
['C2','Draft register and catalogue entries; suggest owners, descriptions and classifications','ATRS where the tool informs decisions; human review of generated metadata','Known, owned and described inputs (the register and the catalogue)','Change'],
['C3','Suggest retention and disposal; support appraisal and sensitivity review at scale','Human decision on every disposal; records of the AI\'s suggestion','Provenance and lifecycle status of training and grounding sources','Change'],
['C4','Find information for FOI and subject access; flag personal data','DPIA; data protection by design; security classification of prompts and outputs','Lawful basis, access rights and classification for every source','BAU'],
['C5','Answer questions from corporate knowledge; capture leaver knowledge','Transparency to users; accuracy checks','Curated, current knowledge sources with owners','Change'],
['C6','Remediate the digital heap; auto-label Microsoft 365 content; capture AI outputs as records','Supplier assurance; tool registration','Prompts, outputs and agent actions kept as records where they evidence decisions','Change'],
['C7','Personalised learning; AI literacy for owners and stewards','Core AI curriculum; acceptable use','Owners and stewards who can judge AI suggestions','BAU'],
['C8','Benefits tracking; legacy migration mapping','Spend and assurance controls for AI tools','Asset value and criticality to prioritise AI investment','Change']
];

const SKILLS=[
['Government Digital and Data Profession Capability Framework','Data roles from data governance manager to chief data officer, with skills at each level.','D','https://ddat-capability-framework.service.gov.uk/role/data-governance-manager'],
['GKIM competency frameworks','Frameworks for KIM roles including information rights, records, information and knowledge management.','I','https://comaea.com/2021/07/25/government-knowledge-and-information-management-profession-choose-comaea-to-build-skills-frameworks-2/'],
['Senior Civil Service digital and data roles','The chief data officer and chief digital and information officer roles, with shared skills.','D','https://ddat-capability-framework.service.gov.uk/role/chief-digital-and-information-officer'],
['Core digital, data, innovation and AI curriculum','Launched April 2026 for all civil servants; AI fundamentals modules.','A','https://analysisfunction.civilservice.gov.uk/ai-hub/ai-learning-and-development/'],
['AI and data scientist accelerators','Cohort upskilling of existing civil servants into AI and data roles.','A','https://technology.blog.gov.uk/2026/03/31/one-year-of-the-ai-accelerator-building-government-tech-talent'],
['AI for GKIM community','Monthly community for KIM professionals using and governing AI.','I','https://www.gov.uk/service-manual/communities/ai-for-government-knowledge-information-management-community'],
['DSPT key roles in health and care','SIRO, Caldicott Guardian, DPO and IG lead roles with expected training.','S','https://dsptoolkit.nhs.uk/Help/Attachment/61'],
['GO-Science Futures Toolkit and training','Three Horizons and other futures tools, with training for public servants.','L','https://www.gov.uk/government/publications/futures-toolkit-for-policy-makers-and-analysts/the-futures-toolkit-html']
];
const LADDER=[
['Awareness','Everyone','Why data is an asset; DAM in a page','Records are evidence; what to keep and where','Using AI tools responsibly','One induction module on assets, records and AI','BAU'],
['Literacy','Everyone who creates or uses data and information','Quality, metadata and sharing basics','File plans, retention and FOI basics','AI fundamentals; checking AI outputs','Shared literacy module built on the core curriculum','BAU'],
['Practitioner','Stewards, information asset managers, records managers','Cataloguing playbook; data quality action plans','IAR guide; disposal reviews; IMA tools','AI-ready datasets; capturing AI outputs as records','One practitioner track on registers and catalogues','Change'],
['Specialist','Data governance managers, KIM professionals, architects','DMBOK-based playbooks; metadata standards','ISO 15489 and Section 46 practice; preservation','ISO/IEC 42001 controls; ATRS records','Joint community of practice and case library','Change'],
['Leader','CDOs, SIROs, departmental record officers, KIM Leaders, IAOs','DAM Policy accountability; reporting','Public Records Act accountability; information risk','AI Playbook accountability','One accountability briefing for owners of any asset','Change']
];
const ROLEX=[
['Senior accountability','Chief data officer','SIRO; KIM Leader; departmental record officer','Senior responsible owner for AI','GDDCF SCS roles; DSPT key roles'],
['Asset accountability','Data owner','Information asset owner','AI system owner','DAM Data Ownership Model; an information accountability model'],
['Day-to-day care','Data steward or custodian','Information asset manager; records manager','AI product or model owner','GDDCF data roles; GKIM frameworks'],
['Specialist governance','Data governance manager','Information manager; information rights officer','AI assurance or ethics lead','GDDCF; GKIM frameworks'],
['Independent advice','Data protection officer','Data protection officer; Caldicott Guardian in health','Data protection officer','UK GDPR; DSPT key roles']
];
const MODELS=[
{id:'M1',name:'Distinct',desc:'Separate leads and teams for data, information and records, privacy and AI, working through governance forums.',ev:[['NHS: SIRO and Caldicott Guardian are distinct but complementary roles','https://ukcgc.uk/key-relationships'],['NHS Wales: the Caldicott Guardian and SIRO roles should go to two separate people','https://dhcw.nhs.wales/ig/ig-documents/ig-toolkit-requirements/ig-management-structure/ig-management-structure-final-v31-pdf/'],['Councils with separate data governance offices','https://www.local.gov.uk/node/8281619']],pros:'Clear statutory accountability; specialist depth; independence of advice.',cons:'Duplicate registers and asks; owners see several frameworks; gaps between remits.',fit:'Large organisations with strong statutory roles',lens:'BAU'},
{id:'M2',name:'Hybrid or dual-hatted',desc:'One person or team holds more than one remit, for example information governance covering data protection, FOI and records, or a chief digital and information officer covering digital and data.',ev:[['Council information governance teams covering data protection, FOI, records and information management','https://www.doncaster.gov.uk/services/the-council-democracy/information-governance'],['Chief digital and information officer roles in central departments','https://ddat-capability-framework.service.gov.uk/role/chief-digital-and-information-officer'],['US Department of State: one officer is both chief data officer and chief AI officer','https://fam.state.gov/FAM/20FAM/20FAM010201.html']],pros:'One register, one ask, fewer hand-offs; good where capacity is thin.',cons:'Conflicts of interest between advice and delivery; one remit can crowd out another.',fit:'Smaller bodies, arm\'s length bodies, councils',lens:'BAU'},
{id:'M3',name:'One leads the other',desc:'One world sets the frame and the other works within it: data leading records, information governance leading data, or security leading both.',ev:[['US: agency chief data officers expected to carry out records management','https://www.Archives.gov/files/records-mgmt/resources/cdo-rm-assessment-report.pdf'],['A council information governance framework covering data quality, information rights and records','https://www.edinburgh.gov.uk/downloads/file/28998/information-governance-policy'],['DWP: information management policy within a security policy suite, an IAO for every asset','https://gov.uk/government/publications/dwp-information-management-policies/dwp-information-management-policy']],pros:'A single line of sight and one operating rhythm.',cons:'The led world\'s specialist needs (evidential value, preservation, data quality) can be underweighted.',fit:'Transformation programmes and machinery of government changes',lens:'Change'}
];
const MODELFIT=[
['Machinery of government change or merger','One leads the other, for the transition only','One line of sight for ownership transfer and records continuity','Change'],
['Large department with statutory roles in place','Distinct, joined by one register and one accountability model','Keeps independence while removing duplicate asks','BAU'],
['Arm\'s length body or small organisation','Hybrid','One team can run the register, catalogue and records together','BAU'],
['AI adoption at scale','Hybrid at the top, distinct specialists beneath','AI touches every remit; one owner, specialist assurance','Change'],
['Wider public sector without DAM Policy obligations','Align voluntarily through shared standards','The DAM Policy applies to departments and arm\'s length bodies; others need a voluntary route','Change']
];
// recurring calendar: lane, month (1-12, 0 = through the year), label, fixed or varies, url
const CLANES=['Central data','Central information and records','AI','Health and care','Devolved','Local government','Awareness days'];
const CAL=[
['Awareness days',1,'Data Protection Day (28 Jan)','fixed','https://openriskmanual.org/wiki/Data_Protection_Day'],
['Awareness days',9,'International Day for Universal Access to Information (28 Sep)','fixed','https://en.unesco.org/commemorations/accesstoinformationday/'],
['Health and care',6,'DSPT final submission (30 Jun)','fixed','https://www.dsptoolkit.nhs.uk/News/161'],
['Health and care',12,'DSPT baseline submission (31 Dec in the 2025 to 2026 cycle)','varies','https://grcsolutions.io/the-nhs-dspt-data-security-and-protection-toolkit-what-you-need-to-know-for-2025-26/'],
['Central information and records',0,'Annual transfer of records turning 20 to The National Archives','fixed','https://www.nationalarchives.gov.uk/about/our-role/transparency/information-management-report/'],
['Central information and records',0,'Information Management Assessments and Section 46 maturity assessments on request','varies','https://www.nationalarchives.gov.uk/information-management/manage-information/ima/'],
['Devolved',0,'Records management plan progress update reviews (voluntary, any time)','varies','https://nrscotland.gov.uk/publications/guidance-for-completion-of-the-progress-update-review-pur'],
['Central data',1,'DAM Policy Baseline Return (2027) then annual returns at the end of March from 2028','varies',''],
['Central data',4,'Quarterly roadmap reports for modern digital government (example: January to March 2026)','varies','https://roadmap-for-modern-digital-government.campaign.gov.uk/about/quarterly-report-january-march-2026/'],
['AI',0,'ATRS records published as tools come into scope','varies','https://www.gov.uk/government/collections/algorithmic-transparency-recording-standard-hub'],
['Local government',0,'Annual information governance reports to council committees','varies','https://www.suffolk.gov.uk/asset-library/information-governance-annual-report-2025-26.pdf']
];
const CALDATED=[
['2026-12-11','DAM playbooks at the Data Catalogue and Analysis Platform working group','v',''],
['2027-06-30','DSPT final submission for the 2026 to 2027 cycle (expected, if the date holds)','d','https://www.dsptoolkit.nhs.uk/News/161'],
];
const OWN=[];
const OWNCHK=[];
const MOREGAPS=[
['GX-1','No published crosswalk between the digital and data capability framework and the GKIM frameworks','Skills'],
['GX-2','Several assurance cycles (Data Maturity Assessment, DAM Policy returns, KIM self-assessment, Section 46 assessments, DSPT, Scottish records plans) with no shared calendar or common evidence','Calendar'],
['GX-3','AI prompts, outputs and agent actions as records sit between the AI Playbook, records guidance and the DAM Policy','AI'],
['GX-4','The DAM Policy applies to departments and arm\'s length bodies; devolved and local bodies need a voluntary route to the same standards','Landscape'],
['GX-5','ATRS records are not yet linked to the information assets and catalogue entries the tools use','AI'],
['GX-6','AI-ready guidance focuses on datasets; unstructured information (documents, email, chat) needs its own readiness route','AI'],
['GX-7','No single owner view across data, information and AI accountabilities for the same asset','Operating models']
];

/* ---- lens state ---- */
const LENS={lens:'',tx:''};
function lensOK(x){return(!LENS.lens||x.lens===LENS.lens)&&(!LENS.tx||!x.tx||x.tx===LENS.tx)}
/* lens bar: see release 2.1 */
const txTag=t=>`<span class="tag tx-${t}">${t}</span>`;
const domName={D:'Data',I:'Information',K:'Knowledge',A:'AI',S:'Security and privacy',L:'Skills'};

function landscape(){const sec=document.getElementById('l-sec'),rel=document.getElementById('l-rel');
 if(sec.options.length<2){sec.innerHTML+=SECTORS.map(s=>`<option>${esc(s)}</option>`).join('');rel.innerHTML+=RELS.map(r=>`<option value="${r}">${r[0].toUpperCase()+r.slice(1)}</option>`).join('')}
 const d=document.getElementById('l-dom').value,q=document.getElementById('l-q').value.trim().toLowerCase();
 const rows=LAND.filter(x=>lensOK(x)&&(!sec.value||x.sec===sec.value)&&(!rel.value||x.rel===rel.value)&&(!d||x.dom.includes(d))&&(!q||(x.t+' '+x.what+' '+x.who).toLowerCase().includes(q)));
 document.getElementById('l-count').textContent=rows.length+' of '+LAND.length+' developments shown'+(LENS.lens||LENS.tx?' (lens applied)':'');
 const max=Math.max(...RELS.map(r=>LAND.filter(x=>x.rel===r).length));
 document.getElementById('relbars').innerHTML=RELS.map(r=>{const n=rows.filter(x=>x.rel===r).length;return `<div class="brow"><span title="${esc(RELTXT[r])}">${r[0].toUpperCase()+r.slice(1)}</span><div class="btrack"><span class="${r==='diverge'?'b-gap':'b-shared'}" style="width:${n/max*100}%"></span></div><span>${n}</span></div>`}).join('');
 document.getElementById('landcards').innerHTML=rows.map(x=>`<article class="jcard" id="${x.id}"><div>${x.dom.map(k=>`<span class="dom ${'DIKA'.includes(k)?k:'A'}" style="${'SL'.includes(k)?'background:#3d5560':''}">${domName[k]}</span>`).join('')}<span class="tag">${esc(x.sec)}</span></div><h3>${esc(x.t)}</h3><p style="margin:0;font-size:14px;color:var(--mute)">${esc(x.who)} · ${esc(x.when)}</p><p style="margin:0">${gl(x.what)}</p><p style="margin:0;font-size:13px"><span class="tag" title="${esc(RELTXT[x.rel])}">${x.rel}</span><span class="tag">${x.lens}</span>${txTag(x.tx)}<span class="tag" title="${esc(HZTXT[x.hz])}">${x.hz}</span>${provTag(x.prov)}${x.url?` · <a href="${esc(x.url)}">Source</a>`:' · internal working file'}</p></article>`).join('')||'<p>No developments match. Clear the lens or filters.</p>';}

function aiView(){const shown=AIROWS.filter(r=>!LENS.lens||r[4]===LENS.lens);
 document.getElementById('aifigs').innerHTML=[[8,'clusters AI can help deliver'],[LAND.filter(x=>x.dom.includes('A')).length,'developments with an AI dimension'],['15%','of Australian agencies apply AI to information management',1],[MOREGAPS.filter(g=>g[2]==='AI').length,'AI-related gaps found',1]].map(f=>`<div class="fig1${f[2]?' hot':''}"><b>${f[0]}</b><span>${esc(f[1])}</span></div>`).join('');
 document.querySelector('#aitable tbody').innerHTML=shown.map(r=>`<tr><td><strong>${esc(ICL[r[0]])}</strong></td><td>${gl(r[1])}</td><td>${gl(r[2])}</td><td>${gl(r[3])}</td><td>${r[4]}</td></tr>`).join('');}

function skillsView(){document.getElementById('skcards').innerHTML=SKILLS.map(s=>`<article class="jcard"><div><span class="dom ${'DIKA'.includes(s[2])?s[2]:'A'}" style="${'SL'.includes(s[2])?'background:#3d5560':''}">${domName[s[2]]}</span></div><h3>${esc(s[0])}</h3><p style="margin:0">${gl(s[1])}</p><p style="margin:0;font-size:13px"><span class="tag v">Verified</span> <a href="${esc(s[3])}">Source</a></p></article>`).join('');
 document.querySelector('#ladder tbody').innerHTML=LADDER.filter(r=>!LENS.lens||r[6]===LENS.lens).map(r=>`<tr><td><strong>${r[0]}</strong></td><td>${gl(r[1])}</td><td>${gl(r[2])}</td><td>${gl(r[3])}</td><td>${gl(r[4])}</td><td>${gl(r[5])}</td></tr>`).join('');
 document.querySelector('#rolex tbody').innerHTML=ROLEX.map(r=>`<tr><td><strong>${r[0]}</strong></td><td>${gl(r[1])}</td><td>${gl(r[2])}</td><td>${gl(r[3])}</td><td>${gl(r[4])}</td></tr>`).join('');}

function modelsView(){document.getElementById('modelcards').innerHTML=MODELS.map(m=>`<article class="jcard" id="${m.id}" style="${LENS.lens&&m.lens!==LENS.lens?'opacity:.55':''}"><h3>${m.id} ${esc(m.name)}</h3><p style="margin:0">${gl(m.desc)}</p><p style="margin:0;font-size:14px"><strong>Strengths:</strong> ${esc(m.pros)}<br><strong>Risks:</strong> ${esc(m.cons)}<br><strong>Typical fit:</strong> ${esc(m.fit)} · <span class="tag">${m.lens}</span></p><ul style="margin:0;padding-left:18px;font-size:14px">${m.ev.map(e=>`<li>${esc(e[0])} <a href="${esc(e[1])}">Source</a></li>`).join('')}</ul></article>`).join('');
 document.querySelector('#modelfit tbody').innerHTML=MODELFIT.filter(r=>!LENS.lens||r[3]===LENS.lens).map(r=>`<tr><td><strong>${esc(r[0])}</strong></td><td>${esc(r[1])}</td><td>${gl(r[2])}</td><td>${r[3]}</td></tr>`).join('');}

function calendarView(){const M=['Through the year','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
 const g=document.getElementById('calgrid');g.style.gridTemplateColumns=`11em repeat(13,minmax(7.5em,1fr))`;
 g.innerHTML=`<div class="ch"></div>${M.map(m=>`<div class="ch">${m}</div>`).join('')}`+CLANES.map(l=>`<div class="cl">${esc(l)}</div>${M.map((m,i)=>`<div class="cc">${CAL.filter(c=>c[0]===l&&c[1]===i).map(c=>`<div class="cev ${c[3]}">${gl(c[2])}${c[4]?` <a href="${esc(c[4])}" aria-label="Source">↗</a>`:''}</div>`).join('')}</div>`).join('')}`).join('');
 document.getElementById('callist').innerHTML=CALDATED.map(e=>`<li class="${e[0]<TODAY?'past':''}"><time datetime="${e[0]}">${fmtDate(e[0])}</time><span>${provTag(e[2])} ${gl(e[1])}${e[3]?` <a href="${esc(e[3])}">Source</a>`:''}</span></li>`).join('');}

function horizonsView(){const g=document.getElementById('hgrid');g.style.gridTemplateColumns='9em repeat(3,minmax(14em,1fr))';
 g.innerHTML=`<div class="ch"></div>${TX.map(t=>`<div class="ch">${t}</div>`).join('')}`+HZ.slice().reverse().map(h=>`<div class="cl"><strong>${h}</strong><br><small>${esc(HZTXT[h].split(': ')[1])}</small></div>${TX.map(t=>`<div class="cc">${LAND.filter(x=>x.hz===h&&x.tx===t&&(!LENS.lens||x.lens===LENS.lens)&&(!LENS.tx||x.tx===LENS.tx)).map(x=>`<a class="hchip" href="#landscape" data-jumpl="${x.id}">${esc(x.t)}</a>`).join('')}</div>`).join('')}`).join('');
 document.getElementById('hread').innerHTML=[['Evolution','Improve what exists: steady-state records transfer, the IMA toolkit, refreshed roles and frameworks. Mostly horizon 1 and business as usual.'],['Reform','Change the rules and structures: the DAM Policy, AI-ready dataset guidelines, the accountability model, the core curriculum. Mostly horizon 2.'],['Revolution','Change the system: the National Data Library, one officer for data and AI, data leaders running records management, a tenth of the Civil Service in digital and data roles. Horizon 3.']].map(r=>`<div class="jcard">${txTag(r[0])}<p style="margin:0">${esc(r[1])}</p></div>`).join('');}


function moreGaps(){const el=document.getElementById('gaplist');el.insertAdjacentHTML('beforeend',`<h2 id="g-more">Further gaps across the landscape <span class="cnt">${MOREGAPS.length}</span></h2><div class="cards">${MOREGAPS.map(x=>`<div class="jcard"><h3>${x[0]} <span class="tag p">Proposed</span></h3><p style="margin:0">${gl(x[1])}</p><p style="margin:0;font-size:13px">See: <a href="#${GXMAP[x[2]]}">${esc(x[2])}</a></p></div>`).join('')}</div>`);}

function renderLensViews(){landscape();aiView();skillsView();modelsView();calendarView();horizonsView();buildToc()}
['l-sec','l-rel','l-dom'].forEach(id=>document.getElementById(id).addEventListener('change',landscape));document.getElementById('l-q').addEventListener('input',landscape);
document.addEventListener('click',e=>{const a=e.target.closest('[data-jumpl]');if(!a)return;setTimeout(()=>{const el=document.getElementById(a.dataset.jumpl);if(el)el.scrollIntoView({behavior:SMOOTH()})},120)});
Object.assign(DATA,{LAND,AIROWS,SKILLS,LADDER,ROLEX,MODELS,CAL,CALDATED,OWN,OWNCHK,MOREGAPS,CLANES});


/* ===== Release 2.1: self-explaining lenses, personas, journeys, pathways, wayfinder ===== */
// What each lens and transformation value means, shown as chip tooltips and in the help panel
const LDEF={'':'Show everything, no lens applied',BAU:'Business as usual: running and improving today\'s arrangements',Change:'Change: programmes, reforms and new arrangements being introduced',Evolution:'Evolution: improve what exists',Reform:'Reform: change the rules and structures',Revolution:'Revolution: change the system itself'};
// Where each lens works. Every view is declared, so the bar can always say what it does on the current view.
// src names the data the lens acts on; lf/tf name the fields holding the lens and transformation tags.
const LENSMAP={
 overview:{note:'The overview summarises everything, so it is not filtered.'},
 start:{note:'Journeys and pathways set the lens for you when a step needs one.'},
 landscape:{lens:'filter',tx:'filter',src:'LAND',lf:'lens',tf:'tx',what:'developments'},
 capabilities:{note:'Capabilities are not tagged: each applies in both business as usual and change.'},
 gaps:{note:'Gaps are not tagged: each needs closing in both business as usual and change.'},
 wheel:{note:'The wheel is a reference model, so it is not tagged.'},
 standards:{note:'Standards are reference material, so they are not tagged.'},
 ai:{lens:'filter',src:'AIROWS',lf:4,what:'AI rows',txnote:'AI rows carry a lens tag but no transformation tag.'},
 skills:{lens:'filter',src:'LADDER',lf:6,what:'learning-route steps',txnote:'Only the learning route is tagged. Frameworks and the role crosswalk always show.'},
 models:{lens:'filter',src:'MODELFIT',lf:3,what:'situations in the fit table',txnote:'Model cards outside the lens are dimmed, not hidden, so the three can still be compared.'},
 calendar:{note:'Calendar entries are fixed dates and cycles, so they are not filtered.'},
 horizons:{lens:'filter',tx:'filter',src:'LAND',lf:'lens',tf:'tx',what:'developments on the grid'},
 glossary:{note:'Reference material, not filtered.'},
 about:{note:'Method and checks, not filtered.'}};
const lensSrc=n=>({LAND,AIROWS,LADDER,MODELFIT,OWN})[n]||[];
function lensMatch(item,m){return(!LENS.lens||item[m.lf]===LENS.lens)&&(!m.tx||!LENS.tx||item[m.tf]===LENS.tx)}
function parseHash(){const raw=(location.hash||'#overview').slice(1);const i=raw.indexOf('?');return{v:i<0?raw:raw.slice(0,i),p:new URLSearchParams(i<0?'':raw.slice(i+1))}}
function curView(){const v=parseHash().v;return VIEWS.some(x=>x[0]===v)?v:'overview'}
const vname=v=>(VIEWS.find(x=>x[0]===v)||[v,v])[1];
// Build a link that opens a view with a lens preset and a section; pathway links also carry the step
function hrefTo(view,opt={}){const p=new URLSearchParams();if(opt.to)p.set('to',opt.to);if('lens' in opt)p.set('lens',opt.lens||'');if('tx' in opt)p.set('tx',opt.tx||'');if(opt.pw){p.set('pw',opt.pw);p.set('s',opt.s)}if(opt.tab)p.set('tab',opt.tab);const q=p.toString();return '#'+view+(q?'?'+q:'')}
function syncHash(){const p=new URLSearchParams();if(LENS.lens)p.set('lens',LENS.lens);if(LENS.tx)p.set('tx',LENS.tx);const q=p.toString();try{history.replaceState(null,'','#'+curView()+(q?'?'+q:''))}catch(e){}}

function lensStatus(v){const m=LENSMAP[v]||{};const on=LENS.lens||LENS.tx;
 if(!m.lens){const where=VIEWS.filter(x=>LENSMAP[x[0]]&&LENSMAP[x[0]].lens).map(x=>`<a href="#${x[0]}">${esc(x[1])}</a>`).join(', ');
  return `<strong>${on?'Lens set, but it has no effect on this view.':'Lenses do not change this view.'}</strong> ${esc(m.note||'')} They filter: ${where}.`}
 const all=lensSrc(m.src),n=all.filter(x=>lensMatch(x,m)).length;
 const txOff=!m.tx?` ${esc(m.txnote||'Transformation tags are not used here.')}`:'';
 return `<strong>${on?`Showing ${n} of ${all.length} ${esc(m.what)}`:`All ${all.length} ${esc(m.what)} shown`}</strong>${on?` (${[LENS.lens,m.tx?LENS.tx:''].filter(Boolean).join(' · ')})`:'. Choose a lens to narrow them.'}${txOff}`}

function lensBar(){const b=document.getElementById('lensbar'),v=curView(),m=LENSMAP[v]||{};const open=!document.getElementById('lenshelp').hidden;
 const chip=(k,val,enabled)=>`<button type="button" class="lchip" data-${k}="${val}" aria-pressed="${LENS[k]===val}" title="${esc(LDEF[val])}"${enabled?'':' disabled'}>${val||'All'}</button>`;
 b.innerHTML=`<button type="button" class="lhelp" id="lhelpbtn" aria-expanded="${open}" aria-controls="lenshelp"><span aria-hidden="true">?</span> How lenses work</button>`
 +`<span class="lgrp" role="group" aria-label="Lens: business as usual or change"><span class="lb">Lens</span>${['','BAU','Change'].map(x=>chip('lens',x,!!m.lens)).join('')}</span>`
 +`<span class="lgrp" role="group" aria-label="Transformation"><span class="lb">Transformation</span>${['',...TX].map(x=>chip('tx',x,!!m.tx)).join('')}</span>`
 +`<span class="lstat" id="lstat" aria-live="polite">${lensStatus(v)}</span>`;}

function lensHelp(){document.getElementById('lenshelp').innerHTML=`<div class="lhgrid"><div><h3>What the lenses mean</h3><dl class="kv">${Object.keys(LDEF).filter(Boolean).map(k=>`<dt>${k}</dt><dd>${esc(LDEF[k].split(': ')[1])}</dd>`).join('')}</dl></div>
 <div><h3>How they work</h3><ul><li><strong>Lens</strong> narrows items to business as usual or change. <strong>Transformation</strong> narrows them to evolution, reform or revolution. Used together, both must match.</li><li>Only items the author has tagged are filtered. The tags are judgement calls, labelled as proposed.</li><li>The choice stays set as you move between views and is saved in the page address, so a link to a filtered view can be shared.</li><li>Chips are greyed out on views that are not tagged, and the line beside the chips says what the lens is doing on the current view.</li><li>Journeys and pathways set the lens for you where a step needs one. <strong>All</strong> clears it.</li></ul></div></div>
 <h3>Where each lens applies</h3>${lensMatrix()}`}
function lensMatrix(){return `<div class="scroll"><table class="stack lmx"><thead><tr><th>View</th><th>Lens</th><th>Transformation</th><th>What it acts on</th></tr></thead><tbody>${VIEWS.map(x=>{const m=LENSMAP[x[0]]||{};return `<tr><td data-l="View"><a href="#${x[0]}">${esc(x[1])}</a></td><td data-l="Lens">${m.lens?(m.lens==='dim'?'Dims':'Filters'):'<span class="off">Not used</span>'}</td><td data-l="Transformation">${m.tx?'Filters':'<span class="off">Not used</span>'}</td><td data-l="Acts on">${m.lens?esc(m.what)+(m.txnote?'. '+esc(m.txnote):''):esc(m.note||'')}</td></tr>`}).join('')}</tbody></table></div>`}

document.getElementById('lensbar').addEventListener('click',e=>{if(e.target.closest('#lhelpbtn')){const h=document.getElementById('lenshelp');h.hidden=!h.hidden;lensBar();return}
 const c=e.target.closest('.lchip');if(!c||c.disabled)return;if('lens' in c.dataset)LENS.lens=c.dataset.lens;if('tx' in c.dataset)LENS.tx=c.dataset.tx;renderLensViews();lensBar();syncHash()});

/* ---- personas: illustrative, built from the roles in this resource, not from user research ---- */
const PERSONAS=[
{id:'P1',title:'Senior data leader',team:'Data',grade:'DD',role:null,goal:'Decide how data and information governance should work together in my organisation without adding to teams\' burden.',needs:['What the two worlds share and where they differ','Options for how to organise','The assurance cycles we must meet'],pains:['Overlapping returns and registers','Two professions with different vocabularies'],asks:['Where could two asks become one?','Which operating model suits us?'],journey:'JR1',path:'PW4'},
{id:'P2',title:'Senior information leader',team:'Information',grade:'DD',role:null,goal:'Give the information and records lifecycle a clear place alongside data asset management, and govern AI use as records.',needs:['What the DAM playbooks do not cover','How others organise the two worlds','A view of AI outputs as records'],pains:['Records and knowledge work treated as an afterthought','Parallel frameworks that confuse owners'],asks:['What is missing for information?','Are AI prompts and outputs records?'],journey:'JR2',path:'PW1'},
{id:'P3',title:'Head of data governance',team:'Data',grade:'G6',role:null,goal:'Plan the next year of data governance work so it joins up with information management and AI governance.',needs:['The year\'s assurance cycles on one calendar','Reforms in flight','A sequence across the three horizons'],pains:['Date clashes found too late','Dependencies held in people\'s heads'],asks:['What lands when?','What should come first?'],journey:'JR3',path:'PW6'},
{id:'P4',title:'Head of knowledge and information management',team:'Information',grade:'G6',role:null,goal:'Line up information management standards and training with data asset management.',needs:['Which standards are shared and which are unique','A training route both professions can use','Where each reform sits on the horizons'],pains:['Standards drafted in parallel','Learning offers that do not join up'],asks:['Which standards do both worlds rely on?','What should training cover first?'],journey:'JR4',path:'PW5'},
{id:'P5',title:'Data governance and catalogue lead',team:'Data',grade:'G7',role:null,goal:'Make our information asset register and data catalogue describe assets the same way.',needs:['The IAR to DCAT field crosswalk','The capability list with information equivalents','The gaps to plan for'],pains:['Register fields that do not map cleanly','No shared vocabulary'],asks:['Which IAR fields map to DCAT?','Which capabilities need an information version?'],journey:'JR5',path:'PW8'},
{id:'P6',title:'Records and information manager',team:'Information',grade:'G7',role:null,goal:'Cover the information-only capabilities by reusing the DAM playbooks\' structure.',needs:['The gaps drilled down to unit of work','Records standards and assurance cycles','Examples from other organisations'],pains:['Building a framework from scratch','Records obligations missed in data-led work'],asks:['What is the unit of work for each gap?','Which records cycles must the plan respect?'],journey:'JR6',path:'PW7'},
{id:'P7',title:'Information asset owner',team:'Business',grade:'Any',role:null,goal:'Understand what owning data and information assets asks of me and my team.',needs:['Plain-language definitions','What skills my team needs','When assurance asks arrive'],pains:['Overlapping returns','Jargon from two professions'],asks:['What does an information asset owner do differently from a data owner?','What will I be asked, and when?'],journey:'JR7',path:'PW1'},
{id:'P8',title:'AI delivery lead',team:'AI',grade:'Any',role:null,goal:'Know which data and information governance my AI tool needs before it goes live.',needs:['What AI governance needs from data and information','Metadata that AI-ready datasets depend on','Where prompts and outputs fall between regimes'],pains:['Governance found late in delivery','Unclear whether outputs are records'],asks:['What must be true of my sources?','Are my prompts and outputs records?'],journey:'JR8',path:'PW3'}];
const STAGES=['Orient','Understand','Decide','Act','Review'];
const JOURNEYS={
JR1:[['Orient','See the overlap at a glance','overview','o-board','','','Knows 26 of 32 capabilities are shared or adaptable'],['Understand','See how other organisations run it','landscape','l-items','BAU','','Real examples in view'],['Decide','Choose an operating model','models','m-fit','','','A model that fits'],['Act','Check the assurance cycles to align','calendar','cal-grid','','','Clashes known'],['Review','Test the decision against reforms on the horizon','horizons','h-grid','Change','Reform','Decision still holds as reforms land']],
JR2:[['Orient','See what is shared and what is missing','overview','o-board','','','The gap is clear'],['Understand','Read the 13 information-only gaps','gaps','','','','Knows what has no home'],['Decide','Pick an operating model for the two worlds','models','m-fit','','','A model that fits'],['Act','Check the standards to build on','standards','s-matrix','','','A standards base'],['Review','Check AI use is governed as records','ai','ai-two','','','AI outputs covered']],
JR3:[['Orient','See the year\'s assurance cycles','calendar','cal-grid','','','Knows the busy months'],['Understand','Review reforms in flight','landscape','l-items','Change','Reform','Reforms and dates in view'],['Decide','Sequence the work across the horizons','horizons','h-grid','','','A sequence'],['Act','Plan the skills the work needs','skills','k-ladder','','','A learning route'],['Review','Check dated milestones','calendar','cal-dated','','','Plan matches the dates']],
JR4:[['Orient','See the overlap at a glance','overview','o-board','','','Shared ground understood'],['Understand','Compare shared and unique standards','standards','s-matrix','','','Knows which standards both use'],['Decide','Place each reform on the three horizons','horizons','h-grid','','','A sequence for standards work'],['Act','Plan training across both professions','skills','k-ladder','','','A learning route'],['Review','Check the role crosswalk','skills','k-roles','','','Roles mapped']],
JR5:[['Orient','Open the IAR to DCAT crosswalk','standards','s-xwalk','','','Sees which fields map'],['Understand','Review the capability list','capabilities','c-list','','','Knows which need an information version'],['Decide','Choose which gaps to cover first','gaps','','','','A first scope'],['Act','Check the metadata AI needs','ai','ai-table','','','AI-ready fields known'],['Review','Check the standards behind the mapping','standards','s-models','','','A sound basis']],
JR6:[['Orient','Read the 13 gaps','gaps','','','','Knows the scope'],['Understand','Reuse the DAM capability structure','capabilities','c-list','','','A template to follow'],['Decide','Choose the standards to build on','standards','s-models','','','A standards base'],['Act','Plan around the records cycles','calendar','cal-grid','','','Plan respects records transfer and assessment cycles'],['Review','Compare with other organisations','landscape','l-items','','','Approach tested against practice']],
JR7:[['Orient','See what both worlds cover','overview','o-board','','','Understands the two worlds'],['Understand','See when assurance asks arrive','calendar','cal-grid','','','Dates in the diary'],['Decide','Find the skills your team needs','skills','k-ladder','','','A learning plan'],['Act','Choose how your team organises','models','m-fit','','','A model for your size of organisation'],['Review','Check unfamiliar terms','glossary','','','','A shared vocabulary']],
JR8:[['Orient','See how AI meets each information cluster','ai','ai-two','','','Knows the two directions'],['Understand','Read what AI governance needs back','ai','ai-table','','','A checklist for sources'],['Decide','Review changes under way','landscape','l-items','Change','','AI-ready guidelines and the National Data Library in view'],['Act','Check source metadata against DCAT','standards','s-xwalk','','','AI-ready metadata'],['Review','Check the gaps where AI falls between regimes','gaps','g-more','','','Risks known before go-live']]};
const PATHS=[
{id:'PW1',title:'Ten-minute orientation',mins:10,for:'Anyone new to the topic',why:'See what the two worlds share, what is missing and which standards they rely on.',steps:[['overview','o-board','','','Coverage board: shared, adapted, data-only and gap capabilities'],['capabilities','c-list','','','The 32 capabilities and how each applies to information'],['gaps','','','','The 13 information-only gaps, drilled down to unit of work'],['standards','s-matrix','','','Which standards each world relies on']]},
{id:'PW2',title:'Join up assurance',mins:20,for:'Senior leaders and heads of team',why:'See the assurance cycles from different regimes and where they could be combined.',steps:[['calendar','cal-grid','','','Recurring cycles by month and regime'],['calendar','cal-dated','','','Dated milestones'],['landscape','l-items','Change','Reform','Reforms changing what organisations must report'],['gaps','g-more','','','Gaps, including the missing shared calendar']]},
{id:'PW3',title:'Make information AI-ready',mins:25,for:'AI teams, data and information leads',why:'Know what AI needs from data and information governance, and what it gives back.',steps:[['ai','ai-two','','','How AI helps deliver each cluster, and what AI governance needs in return'],['standards','s-xwalk','','','IAR to DCAT crosswalk: the metadata AI-ready datasets depend on'],['landscape','l-items','Change','','Change under way: AI-ready guidelines, the National Data Library, ATRS'],['gaps','g-more','','','Gaps where AI prompts and outputs fall between regimes']]},
{id:'PW4',title:'Choose an operating model',mins:15,for:'Senior leaders and heads of team',why:'Compare distinct, dual-hatted and one-leads-the-other arrangements with real examples.',steps:[['models','','','','The three models, with sourced examples'],['models','m-fit','','','Which model fits which situation'],['landscape','l-items','BAU','','How other organisations run it today'],['skills','k-roles','','','How roles line up across the frameworks']]},
{id:'PW5',title:'Build skills and literacy',mins:15,for:'Heads of team, learning leads',why:'Join up the two capability frameworks and a learning route from awareness to leadership.',steps:[['skills','k-frameworks','','','The capability frameworks that govern both professions'],['skills','k-ladder','','','A five-step learning route across data, information and AI'],['skills','k-roles','','','Proposed role crosswalk between the frameworks'],['glossary','','','','A shared vocabulary']]},
{id:'PW6',title:'Plan across three horizons',mins:20,for:'Heads of team and strategy leads',why:'Sequence the work from today\'s system to the future one.',steps:[['horizons','h-grid','','','Every development placed by horizon and transformation'],['horizons','h-read','','','What evolution, reform and revolution mean here'],['landscape','l-items','','Revolution','System-level changes to prepare for'],['calendar','cal-dated','','','Dated milestones']]},
{id:'PW7',title:'Cover the information gaps',mins:15,for:'Records and information leads',why:'Work through the information-only capabilities using the DAM playbooks\' structure.',steps:[['gaps','','','','The 13 gaps, each down to unit of work'],['capabilities','c-list','','','The DAM structure to reuse'],['standards','s-models','','','Standards for records and information'],['calendar','cal-grid','','','Records cycles to plan around']]},
{id:'PW8',title:'From registers to catalogues',mins:20,for:'Data governance, catalogue and register leads',why:'Show how information asset registers and data catalogues realise the standards.',steps:[['standards','s-models','','','Maturity models and standards for both worlds'],['standards','s-xwalk','','','IAR fields mapped to DCAT'],['capabilities','c-list','','','Capabilities the registers and catalogues serve'],['gaps','','','','Where registers need capabilities the catalogue does not cover']]}];
const WTEAMS=[['Data','Data (governance, catalogues, standards)'],['Information','Knowledge, information and records'],['Business','A business area that owns assets'],['AI','An AI delivery team'],['Other','Somewhere else']];
const WLEVELS=[['DD','Senior leader'],['G6','Head of team'],['G7','Lead or manager'],['Other','Another level']];
const WAYGOALS=[['orient','Get oriented','PW1'],['decide','Join up assurance','PW2'],['plan','Plan across the horizons','PW6'],['deliver','Deliver registers and catalogues','PW8'],['ai','Govern AI or make information AI-ready','PW3'],['skills','Build skills and literacy','PW5'],['own','Cover the information gaps','PW7'],['model','Choose how to organise','PW4']];
// Routing rule: pick the persona nearest to the reader, and the pathway that serves their goal
function wayfind(team,level,goal,D){D=D||DATA;
 let p;
 if(team==='Business')p='P7';else if(team==='AI')p='P8';
 else if(team==='Data'||team==='Information'){const g=level==='Other'?'G7':level;p=(D.PERSONAS.find(x=>x.team===team&&x.grade===g)||{}).id}
 else p={DD:'P1',G6:'P3',G7:'P5',Other:'P7'}[level];
 const w=D.WAYGOALS.find(x=>x[0]===goal);return{persona:p,path:w?w[2]:null};}


/* ---- pathway trail: shows where you are on a pathway, with previous and next ---- */
let PATH=null;
function trail(){const t=document.getElementById('trail');const P=PATH&&PATHS.find(x=>x.id===PATH.id);if(!P){t.hidden=true;return}
 const s=Math.max(0,Math.min(PATH.s,P.steps.length-1)),st=P.steps[s],here=curView()===st[0];
 const link=i=>{const x=P.steps[i];return hrefTo(x[0],{to:x[1],lens:x[2],tx:x[3],pw:P.id,s:i})};
 t.hidden=false;t.innerHTML=`<span class="tdot" aria-hidden="true"></span><span><strong>Pathway: ${esc(P.title)}</strong> · step ${s+1} of ${P.steps.length}: ${gl(st[4])}</span>
 <ol class="tsteps" aria-label="Steps">${P.steps.map((x,i)=>`<li><a href="${link(i)}"${i===s?' aria-current="step"':''} title="${esc(x[4])}">${i+1}</a></li>`).join('')}</ol>
 <span class="tnav">${here?'':`<a class="btn ghost" href="${link(s)}">Back to step ${s+1}</a>`}${s>0?`<a class="btn ghost" href="${link(s-1)}">Previous</a>`:''}${s<P.steps.length-1?`<a class="btn" href="${link(s+1)}">Next: ${esc(vname(P.steps[s+1][0]))}</a>`:`<a class="btn" href="${hrefTo('start',{tab:'paths'})}">Finish</a>`}<button type="button" class="btn ghost" id="tleave">Leave pathway</button></span>`;
 document.getElementById('tleave').onclick=()=>{PATH=null;trail()};}

/* ---- the Find your way view ---- */
const WTABS=[['find','Wayfinder','w-find'],['personas','Personas','w-personas'],['journeys','Journeys','w-journeys'],['paths','Pathways','w-paths'],['guide','User guide','w-guide'],['map','Site map','w-map']];
const lensLabel=(l,t)=>[l,t].filter(Boolean).map(x=>`<span class="tag">${x}</span>`).join('');
let JSEL='P1';
function startView(){
 document.getElementById('wtabs').innerHTML=WTABS.map((t,i)=>`<button role="tab" id="wt-${t[0]}" aria-controls="wp-${t[0]}" aria-selected="${i===0}">${t[1]}</button>`).join('');
 const radios=(name,opts)=>opts.map((o,i)=>`<label class="wopt"><input type="radio" name="${name}" value="${o[0]}"${i===0?' checked':''}><span>${esc(o[1])}</span></label>`).join('');
 document.getElementById('wp-find').innerHTML=`<h2 id="w-find">Answer three questions</h2><p>The wayfinder suggests the persona closest to you and a pathway for what you need to do. It updates as you choose.</p>
 <form class="wq" id="wform"><fieldset><legend>1. Where do you work?</legend>${radios('team',WTEAMS)}</fieldset><fieldset><legend>2. What is your level?</legend>${radios('level',WLEVELS)}</fieldset><fieldset><legend>3. What do you need to do?</legend>${radios('goal',WAYGOALS)}</fieldset></form><div id="wres" aria-live="polite"></div>`;
 document.getElementById('wp-personas').innerHTML=`<h2 id="w-personas">Personas</h2><p class="note">Illustrative personas built from the roles and decisions in this resource, not from user research. <span class="tag p">Proposed</span> Test them with real colleagues before relying on them.</p><div class="cards" id="pcards">${PERSONAS.map(personaCard).join('')}</div>`;
 document.getElementById('wp-journeys').innerHTML=`<h2 id="w-journeys">Journeys</h2><p>Each persona's route through the resource, from getting oriented to reviewing the result. Each step opens the right view, at the right section, with the lens already set.</p><div class="pchips" role="group" aria-label="Choose a persona" id="jpick">${PERSONAS.map(p=>`<button type="button" class="lchip" data-jp="${p.id}" aria-pressed="${p.id===JSEL}">${esc(p.title)}</button>`).join('')}</div><div id="jmap"></div>`;
 document.getElementById('wp-paths').innerHTML=`<h2 id="w-paths">Pathways</h2><p>Routes built around a task rather than a person. Start one and a trail at the top of each page shows where you are, with previous and next. Times are estimates.</p><div class="cards" id="pwcards">${PATHS.map(pathCard).join('')}</div>`;
 const GROUPS=[['Where do the two worlds meet?',['overview','capabilities','wheel','joinups','standards','landscape']],['What is missing?',['gaps']],['What do I do, and when?',['roles','calendar','timeline','horizons']],['How do we build the capability?',['skills','models','ai']],['Start with ourselves',['own']],['Reference',['glossary','about']]];
 document.getElementById('wp-map').innerHTML=`<h2 id="w-map">Site map</h2><p>Every view, grouped by the question it answers.</p><div class="cards">${GROUPS.map(g=>[g[0],g[1].filter(v=>VIEWS.some(x=>x[0]===v))]).filter(g=>g[1].length).map(g=>`<div class="jcard"><h3>${esc(g[0])}</h3><ul class="smap">${g[1].map(v=>`<li><a href="#${v}">${esc(vname(v))}</a>${LENSMAP[v]&&LENSMAP[v].lens?' <span class="tag">Lens</span>':''}</li>`).join('')}</ul></div>`).join('')}</div><h2 id="w-lenses">Where the lenses apply</h2>${lensMatrix()}`;
 wayRes();journeyMap();}
function personaCard(p){const P=PATHS.find(x=>x.id===p.path);return `<article class="jcard persona" id="${p.id}"><div class="phead"><span class="pav" aria-hidden="true">${p.grade==='Any'?p.team.slice(0,2):p.grade}</span><div><h3>${esc(p.title)}</h3><span class="tag">${esc(p.team==='GKIM'?'Knowledge and information':p.team)}</span><span class="tag">${esc(p.grade==='Any'?'Any level':p.grade)}</span></div></div>
 <p style="margin:0"><strong>Wants to:</strong> ${gl(p.goal)}</p><p style="margin:0;font-size:14px"><strong>Needs:</strong> ${p.needs.map(gl).join('; ')}</p><p style="margin:0;font-size:14px"><strong>Frustrated by:</strong> ${p.pains.map(gl).join('; ')}</p><p style="margin:0;font-size:14px"><strong>Asks:</strong> ${p.asks.map(x=>'"'+gl(x)+'"').join(' ')}</p>
 <p class="pact"><button type="button" class="btn ghost" data-showj="${p.id}">See their journey</button><a class="btn" href="${hrefTo(P.steps[0][0],{to:P.steps[0][1],lens:P.steps[0][2],tx:P.steps[0][3],pw:P.id,s:0})}">Start: ${esc(P.title)}</a>${p.role?`<a href="#roles" data-role="${p.role}">By role: ${esc(ROLES[p.role].title)}</a>`:''}</p></article>`}
function pathCard(P){return `<article class="jcard" id="${P.id}"><h3>${esc(P.title)}</h3><p style="margin:0;font-size:14px;color:var(--mute)">For ${esc(P.for)} · about ${P.mins} minutes (estimate) · ${P.steps.length} steps</p><p style="margin:0">${gl(P.why)}</p><ol class="psteps">${P.steps.map((s,i)=>`<li><a href="${hrefTo(s[0],{to:s[1],lens:s[2],tx:s[3],pw:P.id,s:i})}">${esc(vname(s[0]))}</a>: ${gl(s[4])} ${lensLabel(s[2],s[3])}</li>`).join('')}</ol><p class="pact"><a class="btn" href="${hrefTo(P.steps[0][0],{to:P.steps[0][1],lens:P.steps[0][2],tx:P.steps[0][3],pw:P.id,s:0})}">Start this pathway</a></p></article>`}
function journeyMap(){const p=PERSONAS.find(x=>x.id===JSEL),J=JOURNEYS[p.journey];
 document.getElementById('jmap').innerHTML=`<p><strong>${esc(p.title)}</strong>: ${gl(p.goal)}</p><ol class="jmap">${J.map((s,i)=>`<li class="jstep"><span class="jst">${i+1}. ${esc(s[0])}</span><p style="margin:0">${gl(s[1])}</p><p style="margin:0;font-size:13px;color:var(--mute)">Outcome: ${gl(s[6])}</p><p style="margin:0;font-size:13px">${lensLabel(s[4],s[5])}</p><a href="${hrefTo(s[2],{to:s[3],lens:s[4],tx:s[5]})}">Open ${esc(vname(s[2]))}</a></li>`).join('')}</ol>`;
 document.querySelectorAll('#jpick .lchip').forEach(b=>b.setAttribute('aria-pressed',b.dataset.jp===JSEL));}
function wayRes(){const f=document.getElementById('wform'),val=n=>f.querySelector(`input[name=${n}]:checked`).value;const r=wayfind(val('team'),val('level'),val('goal'));const p=PERSONAS.find(x=>x.id===r.persona),P=PATHS.find(x=>x.id===r.path);
 document.getElementById('wres').innerHTML=`<div class="wres"><div><h3>Closest persona</h3><p style="margin:0"><strong>${esc(p.title)}</strong>: ${gl(p.goal)}</p><p class="pact"><button type="button" class="btn ghost" data-showj="${p.id}">See their journey</button></p></div><div><h3>Suggested pathway: ${esc(P.title)}</h3><p style="margin:0;font-size:14px;color:var(--mute)">About ${P.mins} minutes (estimate)</p><ol class="psteps">${P.steps.slice(0,3).map(s=>`<li>${esc(vname(s[0]))}: ${gl(s[4])}</li>`).join('')}${P.steps.length>3?`<li>and ${P.steps.length-3} more</li>`:''}</ol><p class="pact"><a class="btn" id="wstart" href="${hrefTo(P.steps[0][0],{to:P.steps[0][1],lens:P.steps[0][2],tx:P.steps[0][3],pw:P.id,s:0})}">Start this pathway</a></p></div></div>`;}
function selectTab(listId,tabId){const b=document.getElementById(tabId);if(b&&b.getAttribute('aria-selected')!=='true')b.click()}
document.getElementById('v-start').addEventListener('change',e=>{if(e.target.closest('#wform'))wayRes()});
document.getElementById('v-start').addEventListener('click',e=>{const j=e.target.closest('[data-jp]');if(j){JSEL=j.dataset.jp;journeyMap();return}
 const s=e.target.closest('[data-showj]');if(s){JSEL=s.dataset.showj;journeyMap();selectTab('wtabs','wt-journeys');document.getElementById('w-journeys').scrollIntoView({behavior:SMOOTH()})}});
document.addEventListener('click',e=>{const a=e.target.closest('a[data-role]');if(!a)return;setTimeout(()=>selectTab('rtabs','rt-'+a.dataset.role),0)});

// Sections that exist in each view, so pathway and journey steps can be checked for dead ends
function sectionMap(){const m={};document.querySelectorAll('.view').forEach(v=>{m[v.dataset.view]=[...v.querySelectorAll('h2[id]')].map(h=>h.id)});return m}
Object.assign(DATA,{MODELFIT,PERSONAS,JOURNEYS,PATHS,WAYGOALS,WTEAMS,WLEVELS,LENSMAP});

/* ===== Release 2.2: information wheel, easy-read summaries, user guide, guided tour ===== */
// The information wheel: the knowledge, information, records and enterprise content counterpart of the DAMA wheel.
// A capability is either a gap id (its chain is reused from GAPS) or [id, name, process, activity, unit of work, related ids, standard ids].
const WFAM={G:['Governance','#1b2b3a'],I:['Information management','#1d5a8a'],R:['Records management','#8a4b12'],E:['Enterprise content management','#2f6b3f'],K:['Knowledge management','#5b3d8f']};
const WHEEL=[
{id:'W00',fam:'G',name:'Information governance and accountability',short:'Governance',what:'The policy, ownership and assurance that hold every other area together.',std:'30301,S46,IGIM',caps:[
 ['W00-1','Senior accountability and the management system','Run a management system for records','Set the records policy and review it every year','Approve the policy with the accountable senior officer and record the decision','CR-01','30301,S46'],
 ['W00-2','Information asset ownership','Give every information asset an owner','Confirm owners after a restructure or machinery of government change','Record a new information asset owner against an asset in the register','CR-07,CR-27','27001,S46'],
 ['W00-3','Assurance and maturity','Assess information management maturity','Run a self-assessment against the Section 46 Code','Score one area and record the evidence behind the score','CR-23','TNA,S46']]},
{id:'W01',fam:'I',name:'Information architecture and classification',short:'Architecture',what:'How information is structured: file plans, functions and shared vocabularies.',std:'15489,IGIM',caps:['IM-02',
 ['W01-2','Taxonomies and controlled vocabularies','Maintain shared vocabularies','Reconcile the terms two business areas use for the same thing','Add a preferred term with its synonyms and scope note','CR-06','23081,DCAT']]},
{id:'W02',fam:'I',name:'Metadata, registers and findability',short:'Metadata',what:'Describing information so people and machines can find, trust and reuse it.',std:'23081,DCAT',caps:['IM-10',
 ['W02-2','Information asset registers','Keep the register complete and current','Review the register entries for one business area','Update an entry\'s owner, location and review date','CR-05,CR-13','27001,DCAT']]},
{id:'W03',fam:'I',name:'Information quality and integrity',short:'Integrity',what:'Keeping information authentic, reliable, complete and usable as evidence.',std:'15489,23081',caps:['IM-12',
 ['W03-2','Reliability and completeness','Check information is complete and fit for its purpose','Sample a record series for completeness','Log a missing record and the action to recover it','CR-08','15489']]},
{id:'W04',fam:'I',name:'Access, disclosure and rights',short:'Access',what:'Finding and releasing information lawfully, and preserving it when the law requires.',std:'S46',caps:['IM-07','IM-08']},
{id:'W05',fam:'I',name:'Information security and privacy',short:'Security',what:'Protecting information by classification, handling rules and lawful use of personal data.',std:'27001',caps:[
 ['W05-1','Classification and handling','Apply security classifications','Check the markings on a shared site','Correct the marking on a document and note why','CR-16','27001'],
 ['W05-2','Personal information and records of processing','Keep records of processing current','Review the processing records behind one register','Link an information asset to its record of processing','CR-17','27001']]},
{id:'W06',fam:'R',name:'Records capture and management',short:'Records',what:'Capturing evidence of business activity, including email, chat and AI-assisted work.',std:'15489,S46',caps:['IM-01','IM-13',
 ['W06-3','Email and chat as records','Manage email and chat as records','Set the retention for a team channel','Move a decision thread into the managed store','','15489,S46']]},
{id:'W07',fam:'R',name:'Retention, appraisal and disposal',short:'Retention',what:'Keeping records for as long as they are needed, then selecting or destroying them on authority.',std:'S46,15489',caps:['IM-03','IM-04']},
{id:'W08',fam:'R',name:'Archives and digital preservation',short:'Archives',what:'Reviewing and transferring records of lasting value, and keeping digital records usable.',std:'OAIS,TNA',caps:['IM-05','IM-06']},
{id:'W09',fam:'E',name:'Content and collaboration platforms',short:'Platforms',what:'Governing the platforms where most content now lives, and clearing the digital heap.',std:'IGIM,TNA',caps:['IM-11',
 ['W09-2','Platform configuration for records','Configure platforms so records are kept','Apply retention labels to a site','Test that a labelled document cannot be deleted early','CR-13','IGIM,30301']]},
{id:'W10',fam:'E',name:'Document and content lifecycle',short:'Lifecycle',what:'Controlling drafts, versions and final copies, and moving content safely when systems change.',std:'15489,OAIS',caps:[
 ['W10-1','Document control and versioning','Control drafts, versions and final copies','Set version rules for a document library','Mark a final version and lock it','CR-10','15489'],
 ['W10-2','Migration and decommissioning','Move content safely when systems change','Plan a content migration with a disposal step','Map a source folder to its target location and retention rule','CR-26','15489,OAIS']]},
{id:'W11',fam:'K',name:'Knowledge capture and sharing',short:'Knowledge',what:'Turning what people know into something others can find and use.',std:'30401',caps:['IM-09',
 ['W11-2','Lessons learned','Capture lessons and reuse them','Run a lessons review at a project stage gate','Publish one lesson with its owner and where it applies','','30401']]},
{id:'W12',fam:'K',name:'Communities, expertise and learning',short:'Communities',what:'Connecting people who know with people who need to know.',std:'30401',caps:[
 ['W12-1','Communities of practice','Sustain communities that share know-how','Run a community session on a common problem','Record the answer in the community\'s shared space','CR-22','30401'],
 ['W12-2','Expertise location','Help people find who knows what','Keep an expertise directory current','Add a person\'s areas of expertise with their consent','','30401']]}];
// One capability record, whichever form it was written in
function wcap(c){if(typeof c==='string'){const g=GAPS.find(x=>x.id===c);return g?{id:g.id,name:g.name,proc:g.proc,act:g.act,unit:g.unit,refs:[g.id],std:[],src:g.src,gap:true}:null}
 return{id:c[0],name:c[1],proc:c[2],act:c[3],unit:c[4],refs:c[5]?c[5].split(','):[],std:c[6]?c[6].split(','):[],src:'',gap:false}}
const WSEL={a:null,c:null,l:1};
function wheelSvg(){const R0=118,R1=262,C=280,ring=WHEEL.slice(1),n=ring.length,step=2*Math.PI/n;
 const pt=(r,t)=>[(C+r*Math.sin(t)).toFixed(1),(C-r*Math.cos(t)).toFixed(1)];
 const seg=(w,i)=>{const t0=i*step+0.012,t1=(i+1)*step-0.012,m=(t0+t1)/2,on=WSEL.a===w.id,off=on?10:0,dx=(off*Math.sin(m)).toFixed(1),dy=(-off*Math.cos(m)).toFixed(1);
  const [a,b]=pt(R1,t0),[c2,d]=pt(R1,t1),[e,f]=pt(R0,t1),[g,h]=pt(R0,t0);const [cx,cy]=pt((R0+R1)/2,m),nx=cx,ny=(+cy-9).toFixed(1),lx=cx,ly=(+cy+9).toFixed(1);
  return `<g class="wseg${on?' on':''}" role="button" tabindex="0" data-w="${w.id}" aria-pressed="${on}" aria-label="${esc(w.id+' '+w.short+': '+w.name+', '+WFAM[w.fam][0]+', '+w.caps.length+' capabilities')}" transform="translate(${dx} ${dy})"><path d="M${a} ${b}A${R1} ${R1} 0 0 1 ${c2} ${d}L${e} ${f}A${R0} ${R0} 0 0 0 ${g} ${h}Z" fill="${WFAM[w.fam][1]}"/><text aria-hidden="true"><tspan x="${nx}" y="${ny}" class="wnum">${w.id}</tspan> <tspan x="${lx}" y="${ly}" class="wlbl">${esc(w.short)}</tspan></text></g>`};
 const hub=WHEEL[0],hon=WSEL.a===hub.id;
 return `<svg viewBox="0 0 560 560" class="wheel" role="group" aria-label="Information wheel: a hub and 12 areas. Select an area to drill down.">${ring.map(seg).join('')}<g class="wseg hub${hon?' on':''}" role="button" tabindex="0" data-w="${hub.id}" aria-pressed="${hon}" aria-label="${esc(hub.id+' Information governance: '+hub.name+', the hub, '+hub.caps.length+' capabilities')}"><circle cx="280" cy="280" r="${R0-8}" fill="${WFAM.G[1]}"/><text aria-hidden="true"><tspan x="280" y="262" class="wnum">${hub.id}</tspan> <tspan x="280" y="284" class="wlbl">Information</tspan> <tspan x="280" y="302" class="wlbl">governance</tspan></text></g></svg>`}
function wheelPanel(){const el=document.getElementById('wpanel');const A=WHEEL.find(w=>w.id===WSEL.a);
 if(!A){el.innerHTML=`<h2 id="w-areas">Areas</h2><p>Select an area on the wheel, or from this list. Each drills down to capability, process, activity and unit of work.</p><ul class="warea">${WHEEL.map(w=>`<li><button type="button" class="wpick" data-w="${w.id}"><span class="wsw" style="background:${WFAM[w.fam][1]}"></span><strong>${w.id}</strong> ${esc(w.name)} <span class="cnt">${w.caps.length}</span></button></li>`).join('')}</ul>`;return}
 const C=WSEL.c?A.caps.map(wcap).find(x=>x.id===WSEL.c):null;
 const crumbs=[['Wheel',{a:null}],[A.id+' '+A.short,{a:A.id,c:null}]];if(C){crumbs.push([C.name,{a:A.id,c:C.id,l:1}]);if(WSEL.l>=2)crumbs.push(['Activity',{a:A.id,c:C.id,l:2}]);if(WSEL.l>=3)crumbs.push(['Unit of work',{a:A.id,c:C.id,l:3}])}
 const bc=`<nav class="wcrumb" aria-label="Drill-down path"><ol>${crumbs.map((c,i)=>`<li>${i<crumbs.length-1?`<button type="button" data-wgo='${JSON.stringify(c[1])}'>${esc(c[0])}</button>`:`<span aria-current="location">${esc(c[0])}</span>`}</li>`).join('')}</ol></nav>`;
 const stds=s=>s.filter(Boolean).map(id=>{const S=STD.find(x=>x.id===id);return S?`<a class="tag" href="#standards" title="${esc(S.what)}">${esc(S.name)}</a>`:''}).join(' ');
 const refs=r=>r.map(id=>`<button class="chip ${relClass((CAPS.find(x=>x.id===id)||GAPS.find(x=>x.id===id)||{rel:'gap'}).rel)}" data-open="${id}" type="button" style="min-height:30px;padding:2px 6px"><b>${id}</b></button>`).join(' ');
 let body;
 if(!C){body=`<h2 id="w-areas">${A.id} ${esc(A.name)}</h2><p><span class="tag" style="border-color:${WFAM[A.fam][1]}">${WFAM[A.fam][0]}</span> ${stds(A.std.split(','))}</p><p>${gl(A.what)}</p><h3>Capabilities <span class="cnt">${A.caps.length}</span></h3><div class="wcaps">${A.caps.map(wcap).map(c=>`<button type="button" class="wcap" data-wc="${c.id}"><strong>${c.id}</strong> ${esc(c.name)}${c.gap?' <span class="tag p">Gap</span>':''}<small>Process: ${esc(c.proc)}</small></button>`).join('')}</div>`}
 else{const L=[['Process',C.proc,'The repeatable way the capability is delivered.'],['Activity',C.act,'One piece of work within the process.'],['Unit of work',C.unit,'The smallest task someone can pick up and finish.']];
  body=`<h2 id="w-areas">${C.id} ${esc(C.name)}</h2><p>${C.gap?'<span class="tag p">Gap: not covered by the DAM playbooks</span> ':''}${stds(C.std)}${C.src?' '+gl(C.src):''}</p>
  <ol class="wchain">${L.map((x,i)=>`<li class="${i<WSEL.l?'open':'shut'}"><span class="wlv">${i+2}. ${x[0]}</span>${i<WSEL.l?`<p style="margin:2px 0">${gl(x[1])}</p><small>${esc(x[2])}</small>`:`<button type="button" class="btn ghost" data-wl="${i+1}">Drill down to ${x[0].toLowerCase()}</button>`}</li>`).join('')}</ol>
  ${WSEL.l<3?'<p><button type="button" class="btn ghost" data-wl="3">Show every level</button></p>':''}${C.refs.length?`<p style="font-size:14px">Related on this page: ${refs(C.refs)}</p>`:''}
  <p class="pact">${(()=>{const i=A.caps.map(wcap).findIndex(x=>x.id===C.id),P=A.caps.map(wcap);return (i>0?`<button type="button" class="btn ghost" data-wc="${P[i-1].id}">Previous capability</button>`:'')+(i<P.length-1?`<button type="button" class="btn ghost" data-wc="${P[i+1].id}">Next capability</button>`:'')})()}</p>`}
 el.innerHTML=bc+body;}
function wheelView(){if(!document.getElementById('wsvg'))return;document.getElementById('wsvg').innerHTML=wheelSvg();
 document.getElementById('wlegend').innerHTML=Object.entries(WFAM).map(([k,f])=>`<span><i style="background:${f[1]}"></i>${f[0]} <span class="cnt">${WHEEL.filter(w=>w.fam===k).length}</span></span>`).join('');
 const all=WHEEL.flatMap(w=>w.caps.map(wcap));
 document.getElementById('wfigs').innerHTML=[[WHEEL.length,'areas, hub included'],[all.length,'capabilities'],[all.length*3,'processes, activities and units of work'],[all.filter(c=>c.gap).length,'drawn from the gap list',1]].map(f=>`<div class="fig1${f[2]?' hot':''}"><b>${f[0]}</b><span>${esc(f[1])}</span></div>`).join('');
 wheelPanel();buildToc();}
function wheelGo(s,focus){Object.assign(WSEL,s);if(!('l' in s)&&s.c)WSEL.l=1;wheelView();const p=new URLSearchParams();if(WSEL.a)p.set('w',WSEL.a);if(WSEL.c){p.set('c',WSEL.c);p.set('l',WSEL.l)}try{history.replaceState(null,'','#wheel'+(p.toString()?'?'+p:''))}catch(e){}
 if(focus){const t=document.querySelector(focus);if(t)t.focus()}}
function wheelParams(p){const a=p.get('w'),c=p.get('c'),l=parseInt(p.get('l'),10);const A=WHEEL.find(w=>w.id===a);
 WSEL.a=A?a:null;WSEL.c=A&&c&&A.caps.map(wcap).some(x=>x.id===c)?c:null;WSEL.l=[1,2,3].includes(l)?l:1;wheelView();}
(()=>{const v=document.getElementById('v-wheel');if(!v)return;
 v.addEventListener('click',e=>{const s=e.target.closest('[data-w]');if(s){wheelGo({a:s.dataset.w===WSEL.a&&!WSEL.c?null:s.dataset.w,c:null,l:1},s.closest('svg')?`[data-w="${s.dataset.w}"]`:'#w-areas');return}
  const c=e.target.closest('[data-wc]');if(c){wheelGo({c:c.dataset.wc,l:1},'#w-areas');return}
  const l=e.target.closest('[data-wl]');if(l){wheelGo({l:+l.dataset.wl});return}
  const g=e.target.closest('[data-wgo]');if(g){wheelGo(Object.assign({c:null,l:1},JSON.parse(g.dataset.wgo)),'#w-areas')}});
 v.addEventListener('keydown',e=>{const s=e.target.closest('.wseg');if(!s)return;
  if(e.key==='Enter'||e.key===' '){e.preventDefault();s.dispatchEvent(new MouseEvent('click',{bubbles:true}));return}
  if(['ArrowRight','ArrowLeft','ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();const ids=WHEEL.map(w=>w.id),i=ids.indexOf(s.dataset.w),n=ids[(i+(e.key==='ArrowRight'||e.key==='ArrowDown'?1:-1)+ids.length)%ids.length];document.querySelector(`.wseg[data-w="${n}"]`).focus()}});})();

/* ---- easy-read summaries: one plain-language line at the top of every view, also the menu tooltip ---- */
const EASY={
 overview:'Most of what the data playbooks cover also applies to information. Thirteen information jobs are missing. Start here for the big picture.',
 start:'Not sure where to go? Answer three questions, follow someone like you, or take the tour.',
 landscape:'What is changing across government and the public sector, and whether it pulls data and information together or apart.',
 capabilities:'The 32 things the data playbooks help you do, and what each means for information.',
 gaps:'Thirteen information jobs the data playbooks do not cover yet, each broken down to a small task.',
 wheel:'A wheel for knowledge, information, records and content, like the DAMA wheel for data. Pick a slice and drill down.',
 standards:'The standards and models each world uses, and how registers and catalogues line up.',
 ai:'How AI can help with each area, and what AI needs from good data and information.',
 skills:'The skills frameworks for each profession, and a learning route from beginner to leader.',
 models:'Three ways organisations arrange these roles, with real examples, and which suits whom.',
 calendar:'When the regular returns, reviews and deadlines fall across the year.',
 horizons:'What is happening now, what is changing next, and what the future could look like.',
 own:'Using both worlds on the directorate\'s own data and information first.',
 joinups:'Seven places where the two programmes\' work can join up, and what each asks.',
 timeline:'Key dates for both programmes, in order.',
 roles:'What Deputy Directors, heads of team and leads need to know and decide.',
 glossary:'Plain meanings for the terms and abbreviations used here.',
 about:'Where the content comes from, how it is labelled and the checks it passes.'};
function easyRead(){document.querySelectorAll('.view').forEach(s=>{const t=EASY[s.dataset.view],h=s.querySelector('h1');if(!t||!h||s.querySelector('.easy'))return;h.insertAdjacentHTML('afterend',`<p class="easy"><span class="easytag">In short</span> ${esc(t)}</p>`)});
 document.querySelectorAll('nav.global a').forEach(a=>{const v=a.getAttribute('href').slice(1);if(EASY[v])a.title=EASY[v]});}

/* ---- user guide: a short manual in the Find your way view ---- */
const GUIDE=[
['Getting around','The menu across the top moves between views; items that do not fit fold into More. The Contents switch opens a drawer listing the sections of the view you are on, with counts and New flags. Every view starts with an In short line in plain language.'],
['Finding your way','Find your way offers four routes: the wayfinder (three questions), personas, journeys and pathways. A pathway shows a trail under the menu with the current step, previous and next, so you can leave and come back.'],
['Lenses','The bar under the menu narrows tagged items to business as usual or change, and to evolution, reform or revolution. The line beside it says what it is doing on the current view; chips are greyed out where nothing is tagged. How lenses work explains each value.'],
['The information wheel','Pick an area on the wheel or from the list. Choose a capability, then drill down to its process, activity and unit of work. The path at the top takes you back up one level at a time.'],
['Details and tooltips','Select any capability or gap for its detail panel. Terms with a dotted underline show a definition when you hover or focus on them; all of them are in the Glossary.'],
['Reading the labels','Verified means read in the named source. Draft means taken from a working document that may change. Proposed is this resource\'s own suggestion. Personas, tags and mappings are proposals for discussion.'],
['Display settings','The Display button at the top right offers larger text, easier spacing, reduced motion and high contrast. Your choice is kept in this browser.'],
['Sharing and offline','The page address keeps the view, lens and drill-down, so a copied link opens the same place. The page is a single file: saved to your computer, it works offline.'],
['Checks','The dot at the top right shows whether the page\'s own checks pass. About and checks lists every check and the defect each one guards against.']];
function guideView(){const el=document.getElementById('wp-guide');if(!el)return;el.innerHTML=`<h2 id="w-guide">User guide</h2><p>How to use this page, in ${GUIDE.length} short sections. For a hands-on version, <a href="${hrefTo(PATHS[0].steps[0][0],{to:PATHS[0].steps[0][1],lens:PATHS[0].steps[0][2],tx:PATHS[0].steps[0][3],pw:PATHS[0].id,s:0})}">take the tour</a>.</p><div class="cards">${GUIDE.map((g,i)=>`<div class="jcard"><h3>${i+1}. ${esc(g[0])}</h3><p style="margin:0">${gl(g[1])}</p></div>`).join('')}</div>`}
// The guided tour is the first pathway, so it uses the same trail, checks and wayfinder routing as the others
const TOUR={id:'PW0',title:'Take the tour',mins:5,for:'Anyone using this page for the first time',why:'Five stops that show how the page works: the board, the lens bar, the wheel, tooltips and the glossary.',steps:[['overview','o-board','','','The coverage board: select any capability or gap to open its detail'],['landscape','l-items','Change','','The lens bar is set to Change: the line beside the chips says what it is showing'],['wheel','w-areas','','','The information wheel: pick an area, then drill down to the unit of work'],['standards','s-xwalk','','','Dotted underlines are tooltips: hover or focus on one for its meaning'],['glossary','','','','Every tooltip term is defined here, and the trail above takes you back']]};
PATHS.unshift(TOUR);WAYGOALS.unshift(['tour','Learn how to use this page','PW0']);
Object.assign(DATA,{WHEEL,EASY,GUIDE});

/* ===== Release 2.3: iconography, motion and display settings ===== */
// Simple line icons (20 by 20, drawn for this page). Decorative: always aria-hidden, the text beside them carries the meaning.
const ICO={grid:'M3 3h6v6H3zM11 3h6v6h-6zM3 11h6v6H3zM11 11h6v6h-6z',radar:'M10 10L16 4M10 3a7 7 0 1 0 7 7M10 6.5a3.5 3.5 0 1 0 3.5 3.5',bars:'M4 16V9M8 16V5M12 16v-6M16 16V7M2 17h16',
 compass:'M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM13 7l-2 4-4 2 2-4z',filter:'M3 4h14l-5.5 6.5V16l-3 1v-6.5z',list:'M7 5h10M7 10h10M7 15h10M3 5h.01M3 10h.01M3 15h.01',
 alert:'M10 3l8 14H2zM10 8v4M10 14.5v.01',wheel:'M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM10 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM10 2v4M10 14v4M2 10h4M14 10h4',layers:'M10 2l8 4-8 4-8-4zM2 10l8 4 8-4M2 14l8 4 8-4',
 book:'M4 3h6a2 2 0 0 1 2 2v12a2 2 0 0 0-2-2H4zM16 3h-4M16 3v12h-4',link:'M8 12l4-4M7 9l-2 2a3 3 0 0 0 4 4l2-2M13 11l2-2a3 3 0 0 0-4-4l-2 2',sparkle:'M10 2l2 5 5 2-5 2-2 5-2-5-5-2 5-2z',
 cap:'M2 8l8-4 8 4-8 4zM5 9.5V14c3 2 7 2 10 0V9.5',target:'M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM10 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM10 9.5v1',calendar:'M3 5h14v12H3zM3 9h14M7 3v4M13 3v4',
 route:'M5 15a2 2 0 1 0 0 .01M15 5a2 2 0 1 0 0 .01M5 13V9a3 3 0 0 1 3-3h5',home:'M3 10l7-6 7 6v7H3zM8 17v-5h4v5',users:'M7 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 17c0-3 2-5 5-5s5 2 5 5M13 9a3 3 0 0 0 0-6M15 12c2 .5 3 2.5 3 5',
 clock:'M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM10 5v5l3 2',tag:'M3 3h7l7 7-7 7-7-7zM7 7h.01',check:'M4 10l4 4 8-8',help:'M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM7.5 7.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5M10 14h.01',
 map:'M2 5l5-2 6 2 5-2v12l-5 2-6-2-5 2zM7 3v12M13 5v12',eye:'M1.5 10S5 4 10 4s8.5 6 8.5 6-3.5 6-8.5 6-8.5-6-8.5-6zM10 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4z',scales:'M10 3v14M4 17h12M3 7h14M5 7l-2 5h4zM15 7l-2 5h4z',
 play:'M6 4l10 6-10 6z',flag:'M4 17V3M4 3h10l-2 3 2 3H4',shield:'M10 2l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V5z',type:'M4 5V3h12v2M10 3v14M7 17h6'};
const ico=(n,cls='hi')=>ICO[n]?`<svg class="${cls}" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="${ICO[n]}"/></svg>`:'';
// Heading id prefixes to icons; longest prefix wins, so every section heading has a fitting icon
const H2ICON=[['o-board','grid'],['o-scan','radar'],['o-clusters','bars'],['o-next','clock'],['o-start','compass'],['c-filter','filter'],['c-list','list'],['g-more','flag'],['g-','alert'],['w-wheel','wheel'],['w-areas','layers'],
 ['w-find','compass'],['w-personas','users'],['w-journeys','route'],['w-paths','map'],['w-guide','help'],['w-map','map'],['w-lenses','eye'],['s-models','book'],['s-matrix','grid'],['s-xwalk','link'],['l-summary','bars'],['l-filter','filter'],['l-items','list'],
 ['ai-','sparkle'],['k-frameworks','book'],['k-ladder','cap'],['k-roles','users'],['m-','target'],['cal-grid','calendar'],['cal-dated','clock'],['h-grid','route'],['h-read','book'],['own-types','home'],['own-check','check'],['own-mog','shield'],
 ['j-','link'],['t-','clock'],['r-','users'],['a-prov','tag'],['a-case','scales'],['a-sources','book'],['a-schedule','clock'],['a-checks','check'],['a-log','list']];
const h2icon=id=>{const m=H2ICON.filter(x=>id.startsWith(x[0])).sort((a,b)=>b[0].length-a[0].length)[0];return m?m[1]:null};
const STAGEICO={Orient:'compass',Understand:'book',Decide:'scales',Act:'play',Review:'check'};
function decorate(){
 document.querySelectorAll('h2[id]').forEach(h=>{if(h.querySelector('svg.hi'))return;const n=h2icon(h.id);if(n)h.insertAdjacentHTML('afterbegin',ico(n))});
 document.querySelectorAll('.view').forEach(s=>{const h=s.querySelector('h1');if(!h||h.querySelector('.vtile'))return;const v=VIEWS.find(x=>x[0]===s.dataset.view);if(v)h.insertAdjacentHTML('afterbegin',`<span class="vtile" aria-hidden="true"><svg viewBox="0 0 20 20" focusable="false"><path d="${v[2]}"/></svg></span>`)});
 document.querySelectorAll('.jst').forEach(j=>{if(j.querySelector('svg'))return;const n=STAGEICO[j.textContent.replace(/^\d+\.\s*/,'').trim().replace(/^./,c=>c.toUpperCase()).replace(/(\w)(\w*)/,(m,a,b)=>a+b.toLowerCase())];if(n)j.insertAdjacentHTML('afterbegin',ico(n,'hi sm'))});}
const textOf=h=>[...h.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim();

/* ---- display settings: larger text, easier spacing, reduced motion, high contrast ---- */
const DISP=[['lg','Larger text','Makes all text about an eighth bigger'],['sp','Easier spacing','More space between lines, words and letters, which helps many readers, including some dyslexic readers'],['rm','Reduce motion','Turns off animation and smooth scrolling'],['hc','High contrast','Stronger text and borders']];
function dispApply(on){DISP.forEach(d=>document.documentElement.classList.toggle('d-'+d[0],on.includes(d[0])));try{localStorage.setItem('age-display',on.join(','))}catch(e){}
 document.querySelectorAll('#dispmenu input').forEach(i=>i.checked=on.includes(i.value));}
function dispInit(){const row=document.querySelector('.mrow'),st=document.getElementById('stat');if(!row||document.getElementById('dispbtn'))return;
 st.insertAdjacentHTML('beforebegin',`<div class="disp"><button type="button" class="dispbtn" id="dispbtn" aria-expanded="false" aria-controls="dispmenu">${ico('type','hi')}<span>Display</span></button><div class="dispmenu" id="dispmenu" role="group" aria-label="Display settings" hidden>${DISP.map(d=>`<label class="dopt"><input type="checkbox" value="${d[0]}"><span><strong>${d[1]}</strong><small>${esc(d[2])}</small></span></label>`).join('')}<p class="dnote">Saved in this browser only. Your browser and system settings, such as zoom and reduced motion, still apply.</p></div></div>`);
 const b=document.getElementById('dispbtn'),m=document.getElementById('dispmenu');
 b.addEventListener('click',()=>{m.hidden=!m.hidden;b.setAttribute('aria-expanded',!m.hidden)});
 m.addEventListener('change',()=>dispApply([...m.querySelectorAll('input:checked')].map(i=>i.value)));
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!m.hidden){m.hidden=true;b.setAttribute('aria-expanded','false');b.focus()}});
 document.addEventListener('click',e=>{if(!m.hidden&&!e.target.closest('.disp')){m.hidden=true;b.setAttribute('aria-expanded','false')}});
 let saved='';try{saved=localStorage.getItem('age-display')||'';}catch(e){}dispApply(saved.split(',').filter(x=>DISP.some(d=>d[0]===x)));}
Object.assign(DATA,{H2ICON,DISP});

/* boot */
dispInit();
figs();board();cbars();capFilters();capTable();gaps();moreGaps();renderLensViews();stdCards();matrix();xwalk();startView();guideView();wheelView();easyRead();lensHelp();DATA.SECTIONS=sectionMap();glossary();about();window.__NCHK=selfCheck(DATA,TODAY).length;
wireTabs('stabs');wireTabs('wtabs');
let open=innerWidth>900;try{const s=localStorage.getItem('age-drawer');if(s!==null&&innerWidth>900)open=s==='1';}catch(e){}setDrawer(open);
function mastH(){const M=document.querySelector('header.mast'),h=getComputedStyle(M).position==='sticky'?M.offsetHeight:0,t=document.getElementById('trail');document.documentElement.style.setProperty('--mast-h',h+'px');document.documentElement.style.scrollPaddingTop=(h+(t.hidden?0:t.offsetHeight+12)+8)+'px'}
route();fitNav();mastH();new ResizeObserver(()=>{fitNav();mastH()}).observe(document.querySelector('header.mast'));
window.__AGE={selfCheck,DATA};
{const nj=document.getElementById('nojs');if(nj)nj.remove();}
}
