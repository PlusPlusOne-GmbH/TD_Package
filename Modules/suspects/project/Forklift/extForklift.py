'''Info Header Start
Name : extForklift
Author : Wieland PlusPlusOne@AMB-ZEPH15
Saveorigin : Project.toe
Saveversion : 2023.31378
Info Header End'''


from tempfile import TemporaryDirectory
from pathlib import Path
import json
import sys
from os import listdir
from uuid import uuid4
import inspect
from itertools import chain

class extForklift:
	"""
	extForklift description
	"""
	def __init__(self, ownerComp):
		# The component to which this extension is attached
		self.ownerComp = ownerComp

	def createMetaComp(self, targetComp):
		metaComp:COMP = targetComp.copy(self.ownerComp.op("Package_Meta_Prefab"), name = "Package_Meta")
		ui.messageBox("New Setup", "It seems like you are preparing a COMP. Please take a moment to fill out some Meta-Data")
		metaComp.openParameters()
		metaComp.openViewer()
		metaComp.op("ReadmeRepo").Repo.openViewer()
		return metaComp


	def Build(self, targetComp, publish = True, TempOutput = True):
		with TemporaryDirectory() as _buildDir:
			if not TempOutput:
				_buildDir = Path("TDImportCache", str(uuid4()))
				_buildDir.mkdir( parents=True, exist_ok = False)
			self.PrepareComp( targetComp )
			self.PrepareBuild( targetComp, _buildDir)
			self.ExecuteBuild( _buildDir )
			if publish: self.ExecutePublish( _buildDir )
			self.ownerComp.op("logger").Log("Finished", _buildDir)

	def PrepareComp(self, targetComp:COMP):
		metaComp = targetComp.op("Package_Meta") or self.createMetaComp(targetComp)
		metaComp.par.clone.val = self.ownerComp.op("Package_Meta")
		metaComp.par.enablecloningpulse.pulse()
		metaComp.par.clone.val = ""
		for linkTarget in [
			("Vcname", "Name"),
			("Vcversion", "Version1"),
			("Vcbuild", "Version2"),
		]:
			if hasattr( targetComp.par, linkTarget[0]):
				metaComp.par[linkTarget[1]].bindExpr = f"parent().par['{linkTarget[0]}']"
	

	def cleanExternalDependencies(self, targetComp, parName):
		for childComp in targetComp.findChildren( parName = parName):
			if "KeepExternal" in childComp.tags or childComp.par[parName].mode != ParMode.CONSTANT: continue
			childComp.par[parName].val = ""
	
	def fetchDatDepdencies(self, moduleOp:textDAT ):
		returnData =  [
			op(_member[1].__module__) for _member in inspect.getmembers( mod(moduleOp) ) 
			if (
				_member[0] not in {"mod", "me", moduleOp.name} and 
				hasattr(_member[1], "__module__") and 
				op(_member[1].__module__) is not None and 
				op(_member[1].__module__) is not moduleOp
			)
		]
		return returnData + list(chain.from_iterable([self.fetchDatDepdencies( _dependencyModule ) for _dependencyModule in returnData]))


	def fetchExtDependencies(self, compWithExtensions:COMP):
		return [
			op(extension.__module__) for extension in compWithExtensions.extensions
		]

	def SaveComp(self, targetComp:COMP, targetDir:Path):
		# First we find all textDats that might be interresting for typehinting reasons. 
		self.cleanExternalDependencies( targetComp, "externaltox")
		self.cleanExternalDependencies( targetComp, "file")
		
		# Lets iterate over all extensions
		extensionDats = self.fetchExtDependencies( targetComp )
		debug( [ self.fetchDatDepdencies( extensionDat ) for extensionDat in extensionDats] )
		for moduleDat in set(extensionDats + list(chain.from_iterable( [ self.fetchDatDepdencies( extensionDat ) for extensionDat in extensionDats] ))) :
			moduleDat.save(
				Path( 
					targetDir, 
					*targetComp.relativePath( moduleDat ).split("/")[1:]
				).with_name( moduleDat.name ).with_suffix( f".{moduleDat.par.extension.eval()}"),
				createFolders=True
			)
		
		return Path( targetComp.save( Path(targetDir, targetComp.name).with_suffix(".tox")) )


	def PrepareBuild(self, _targetComp:COMP, _buildDir):
		targetComp = self.ownerComp.op("Schleuse").copy( _targetComp )
		metaComp = targetComp.op("Package_Meta")
		
			
		buildDir = Path( _buildDir )
		buildDir.mkdir(exist_ok=True, parents=True)
		metaComp.op("LicenseRepo").Repo.save(
			Path(buildDir, "LICENSE")
		)
		metaComp.op("ManifestRepo").Repo.save(
			Path(buildDir, "MANIFEST.in")
		)
		metaComp.op("ReadmeRepo").Repo.save(
			Path(buildDir, "README.md")
		)




		with Path(buildDir, "pyproject.toml").open("+wt") as projectToml:
			projectToml.write(
				self.ownerComp.op("prefabPyProject").text.format(**{
					"Name" : f"tdp-{metaComp.par.Name.eval()}",
					"Version" : f"{metaComp.par.Version1}.{metaComp.par.Version2}",
					"Dependencies" : json.dumps([
						cell.val for cell in ( 
							targetComp.op("dependencies") or 
							self.ownerComp.op("empty")
						).col(0)
					]),
					"Authors" : json.dumps([{
						"name" : block.par.Name.eval(), "email" : block.par.Email.eval()
					} for block in metaComp.seq.Authors]).replace(":", "="), #Oh my god. Why python WHY? Why use TOML, not have a writer in hand and then NOT AHDEAR TO JSON!!!
					"Description" : metaComp.par.Description.eval(),
					"License" : metaComp.par.License.eval(),
					"PythonVersion" : f">={sys.version_info.major}.{sys.version_info.minor}",
					"Keywords" : json.dumps(["TouchDesigner", app.build] + [
						block.par.Keyword.eval() for block in metaComp.seq.Keywords
					]),
					"URLs" : f"\n".join([
						f'{block.par.Name.eval()}="{block.par.Url.eval()}"' for block in metaComp.seq.Urls
					]),
					"Build" : app.build
				})
			)

		srcFolder = Path(buildDir, "src", metaComp.par.Name.eval() )
		srcFolder.mkdir( parents=True, exist_ok=True)
		savedTox = self.SaveComp( targetComp, srcFolder )
		
		with Path( srcFolder , "__init__.py").open("+wt") as initFile:
			initFile.write(
				self.ownerComp.op("prefabInit").text.format(**{
					"Filename" : savedTox.name,
					"Version" : f"{metaComp.par.Version1}.{metaComp.par.Version2}"
				})
			)
		targetComp.destroy()
		return buildDir
		
	def ExecuteBuild(self, buildDir:Path):
		with self.ownerComp.op("TD_Conda").EnvShell() as BuildShell:
			BuildShell.Execute(f"cd {buildDir.absolute()}")
			BuildShell.Execute("python -m build")


	def ExecutePublish(self, buildDir:Path):
		"""
			Actually Upload to the repository using twine.
			Right now actually uses cloudsmith. Wold 
		"""
		if not Path(".pypirc").is_file():
			raise Exception("Missing .pypirc file for twine!")
		with self.ownerComp.op("TD_Conda").EnvShell() as BuildShell:	
			BuildShell.Execute(f"python -m twine upload {buildDir}\\dist\\*.whl -r {self.ownerComp.par.Index.eval()} --config-file .pypirc --verbose")
		return
		# Might not be needed actually
		for _subItem in listdir(Path(buildDir, "dist")):
			subItem = Path(buildDir, "dist", _subItem)
			debug( subItem )
			if subItem.is_file() and subItem.suffix == ".whl":
				with self.ownerComp.op("TD_Conda").EnvShell() as BuildShell:
					#BuildShell.Execute(f"cd {buildDir.absolute()}")
					BuildShell.Execute(f"python -m twine upload -r cloudsmith {subItem} --config-file .pypirc")
					break
